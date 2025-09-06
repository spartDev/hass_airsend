"""AirSend switches."""
from typing import Any
import time
import asyncio

from .device import Device

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    ATTR_POSITION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import async_call_later
from homeassistant.const import CONF_DEVICES, CONF_INTERNAL_URL

from . import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
) -> None:
    if discovery_info is None:
        return
    for name, options in discovery_info[CONF_DEVICES].items():
        device = Device(name, options, discovery_info[CONF_INTERNAL_URL])
        if device.is_cover:
            entity = AirSendCover(
                hass,
                device,
            )
            async_add_entities([entity])


class AirSendCover(CoverEntity, RestoreEntity):
    """Representation of an AirSend Cover."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: Device,
    ) -> None:
        """Initialize a cover device."""
        self._hass = hass
        self._device = device
        uname = DOMAIN + device.name
        self._unique_id = "_".join(x for x in uname)
        # Initialize as open to allow control
        self._closed = False
        
        # Position tracking for type 4099 devices
        if device.is_cover_with_position:
            self._attr_current_cover_position = 50
            self._is_opening = False
            self._is_closing = False
            self._movement_start_time = None
            self._movement_start_position = None
            self._target_position = None
            self._position_update_task = None

    async def async_added_to_hass(self):
        """Restore last known state when added to hass."""
        await super().async_added_to_hass()
        
        # Get the last known state
        last_state = await self.async_get_last_state()
        
        if last_state:
            # Restore position for covers with position support
            if self._device.is_cover_with_position:
                if last_state.attributes.get('current_position') is not None:
                    position = last_state.attributes['current_position']
                else:
                    position = 50  # Default position
                
                # Override position based on state if fully open/closed
                if last_state.state == 'closed':
                    position = 0
                elif last_state.state == 'open':
                    position = 100
                    
                # Use centralized state update
                self._attr_current_cover_position = position
                self._closed = (position == 0)
            
            # Restore closed/open state for all covers
            if last_state.state == 'closed':
                self._closed = True
            elif last_state.state == 'open':
                self._closed = False

    @property
    def unique_id(self):
        """Return unique identifier of remote device."""
        return self._unique_id

    @property
    def available(self):
        return True

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._device.name

    @property
    def extra_state_attributes(self):
        return self._device.extra_state_attributes

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self._device.is_async and self._hass:
            component = self._hass.states.get(self.entity_id)
            if component is not None:
                if component.state == 'open' or component.state == 'on' or component.state == 'up':
                    self._closed = False
                else:
                    self._closed = True
        return self._closed
    
    @property
    def is_opening(self):
        """Return if the cover is opening."""
        if self._device.is_cover_with_position:
            return self._is_opening
        return False
    
    @property
    def is_closing(self):
        """Return if the cover is closing."""
        if self._device.is_cover_with_position:
            return self._is_closing
        return False
    
    @property
    def _is_moving(self):
        """Return if the cover is currently moving."""
        return self._is_opening or self._is_closing
    
    @property
    def supported_features(self):
        """Return supported features."""
        if self._device.is_cover_with_position:
            return (
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.STOP
                | CoverEntityFeature.SET_POSITION
            )
        return CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        note = {"method": 1, "type": 0, "value": "UP"}
        if self._device.transfer(note, self.entity_id) == True:
            if self._device.is_cover_with_position:
                # Use the safe movement start method
                self._start_movement(target_position=100, is_opening=True)
            else:
                # Only set open for non-position covers
                self._closed = False
            self.schedule_update_ha_state()

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        note = {"method": 1, "type": 0, "value": "DOWN"}
        if self._device.transfer(note, self.entity_id) == True:
            # Don't immediately set closed for position covers
            if self._device.is_cover_with_position:
                # Use the safe movement start method
                self._start_movement(target_position=0, is_opening=False)
            else:
                # Only set closed for non-position covers
                self._closed = True
            self.schedule_update_ha_state()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        note = {"method": 1, "type": 0, "value": "STOP"}
        if self._device.transfer(note, self.entity_id) == True:
            if self._device.is_cover_with_position:
                # Calculate current position
                if self._movement_start_time and self._movement_start_position is not None:
                    position = self._calculate_position_from_time()
                    # Use centralized state update (but don't schedule HA update yet)
                    self._attr_current_cover_position = position
                    self._closed = (position == 0)
                # Stop movement
                self._is_opening = False
                self._is_closing = False
                if self._position_update_task:
                    self._position_update_task()  # Call the cancel function
                    self._position_update_task = None
            else:
                # For non-position covers, stopping means partially open
                self._closed = False
            self.schedule_update_ha_state()

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = int(kwargs.get(ATTR_POSITION, 0))
        # Clamp position to valid range [0, 100]
        position = max(0, min(100, position))
        
        # If already moving, calculate current position first
        if self._device.is_cover_with_position and self._is_moving and self._movement_start_time:
            current_position = self._calculate_position_from_time()
            self._attr_current_cover_position = current_position
        else:
            current_position = self._attr_current_cover_position
        
        if position == current_position:
            return
        
        # Try direct position command first
        position_note = {"method": 1, "type": 9, "value": position}
        success = False
        try:
            success = self._device.transfer(position_note, self.entity_id)
        except:
            pass
        
        # Fallback to direction-based movement with time tracking
        if not success and self._device.is_cover_with_position:
            if position > current_position:
                note = {"method": 1, "type": 0, "value": "UP"}
                is_opening = True
            else:
                note = {"method": 1, "type": 0, "value": "DOWN"}
                is_opening = False
            
            success = self._device.transfer(note, self.entity_id)
            
        if success:
            if self._device.is_cover_with_position:
                # Use the safe movement start method
                self._start_movement(target_position=position, is_opening=(position > current_position))
            else:
                # Use centralized state update for non-position covers
                self._update_cover_state(position)
                return  # _update_cover_state already schedules HA update
            self.schedule_update_ha_state()
    
    def _update_cover_state(self, position: int):
        """Centralize state updates for position and closed state."""
        self._attr_current_cover_position = position
        self._closed = (position == 0)
        self.schedule_update_ha_state()
    
    def _start_movement(self, target_position: int, is_opening: bool):
        """Safely start a new movement, accounting for any in-progress movement."""
        if not self._device.is_cover_with_position:
            return
        
        # Validate and clamp target position to valid range
        target_position = max(0, min(100, target_position))
        
        # If already moving, calculate and save current position first
        if self._is_moving and self._movement_start_time and self._movement_start_position is not None:
            current_pos = self._calculate_position_from_time()
            self._attr_current_cover_position = current_pos
        else:
            current_pos = self._attr_current_cover_position
        
        # Now start new movement from the actual current position
        self._movement_start_time = time.time()
        self._movement_start_position = current_pos
        self._target_position = target_position
        self._is_opening = is_opening
        self._is_closing = not is_opening if target_position in [0, 100] else (target_position < current_pos)
        
        # Cancel previous position update task if exists
        if self._position_update_task:
            self._position_update_task()  # Call the cancel function
        
        # Schedule new position updates
        self._schedule_position_updates()
    
    def _calculate_position_from_time(self) -> int:
        """Calculate current position based on elapsed time."""
        if not self._movement_start_time or self._movement_start_position is None:
            return self._attr_current_cover_position
        
        elapsed_time = time.time() - self._movement_start_time
        
        if self._is_opening:
            duration = max(1.0, self._device.opening_duration)  # Defensive minimum
            position_change = min((elapsed_time / duration) * 100, 100)  # Cap at 100%
            new_position = min(100, self._movement_start_position + position_change)
        elif self._is_closing:
            duration = max(1.0, self._device.closing_duration)  # Defensive minimum
            position_change = min((elapsed_time / duration) * 100, 100)  # Cap at 100%
            new_position = max(0, self._movement_start_position - position_change)
        else:
            new_position = self._attr_current_cover_position
        
        return int(new_position)
    
    def _schedule_position_updates(self):
        """Schedule periodic position updates."""
        if self._device.is_cover_with_position and (self._is_opening or self._is_closing):
            # Schedule next update in 0.5 seconds
            self._position_update_task = async_call_later(
                self._hass, 0.5, self._update_position_callback
            )
    
    def _update_position_callback(self, _):
        """Callback to update position."""
        self._update_position()
        
    def _update_position(self):
        """Update position during movement."""
        if not self._device.is_cover_with_position:
            return
        
        # Calculate current position
        current_position = self._calculate_position_from_time()
        
        # Check if we've reached target or limits
        stop_movement = False
        if self._target_position is not None:
            if self._is_opening and current_position >= self._target_position:
                current_position = self._target_position
                stop_movement = True
            elif self._is_closing and current_position <= self._target_position:
                current_position = self._target_position
                stop_movement = True
        
        if current_position >= 100:
            current_position = 100
            stop_movement = True
        elif current_position <= 0:
            current_position = 0
            stop_movement = True
        
        # Update position and state using centralized method
        # Don't schedule HA update yet, we'll do it at the end
        self._attr_current_cover_position = current_position
        self._closed = (current_position == 0)
        
        if stop_movement:
            # Stop movement
            self._is_opening = False
            self._is_closing = False
            # Send stop command if we reached target position
            if self._target_position is not None and current_position == self._target_position:
                try:
                    note = {"method": 1, "type": 0, "value": "STOP"}
                    self._device.transfer(note, self.entity_id)
                except:
                    pass
        else:
            # Schedule next update
            self._schedule_position_updates()
        
        self.schedule_update_ha_state()
