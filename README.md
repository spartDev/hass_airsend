<img align="left" width="80" src="https://raw.githubusercontent.com/devmel/hass_airsend/master/icons/icon.png" alt="App icon">

# AirSend for Home Assistant

Component for sending radio commands through the AirSend (RF433) or AirSend duo (RF433 & RF868).

## Installation Steps

1. **Add Repository**:
   - [![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fdevmel%2Fhass_airsend-addon)
   - Click on "Add repository" to include the necessary repository for the addon installation or follow [hass_airsend-addon](https://github.com/devmel/hass_airsend-addon)

2. **Place the `airsend.yaml` File**:
   - Go to `airsend.cloud -> import/export -> Export`
   - Select your devices, for local connection, select `spurl`
   - Click `Export YAML` to save the airsend.yaml
   - In the `config` folder of Home Assistant, place the `airsend.yaml` file.

3. **Edit the `secrets.yaml` File**:
   - Add a line to the `secrets.yaml` file with the AirSend - Local IP - / - Password - (and IPv4 address).
   - If you know the IPv4 address, the line should look like this:
     ```yaml
     spurl: sp://**************@[fe80::xxxx:xxxx:xxxx:xxxx]?gw=0&rhost=192.168.xxx.xxx
     ```
   - or this if you don't know the IPv4 address :
     ```yaml
     spurl: sp://**************@[fe80::xxxx:xxxx:xxxx:xxxx]?gw=1
     ```
   - Replace `**************` with the AirSend Password, `fe80::xxxx:xxxx:xxxx:xxxx` with AirSend Local IP and `192.168.xxx.xxx` with the AirSend IPv4 address.

4. **Edit the `configuration.yaml` File**:
   - Add the following line to the `configuration.yaml` file to include the `airsend.yaml` file:
     ```yaml
     airsend: !include airsend.yaml
     ```

5. **Install the Custom Component**:
   - In the Home Assistant terminal, run the following command to install the component:
     ```bash
     wget -q -O - https://raw.githubusercontent.com/devmel/hass_airsend/master/install | bash -
     ```

6. **Restart Home Assistant and the AirSend Addon**:
   - Restart Home Assistant.
   - Restart the AirSend addon.

These steps will integrate AirSend with Home Assistant, allowing you to manage and automate AirSend-related tasks through the Home Assistant interface.


## Information 

   - This requires the execution of [hass_airsend-addon](https://github.com/devmel/hass_airsend-addon), if it is not on the same machine it is possible to add the field `internal_url: http://x.x.x.x:33863/` in airsend.conf
   - For local connection, the AirSend IPv4 address is required, you can find it in your router or [Airsend App for Windows](https://apps.microsoft.com/detail/9nblggh40m8w).

## Position Tracking for Covers

The integration now supports time-based position tracking for cover devices (type 4099), enabling percentage control through a slider in the Home Assistant UI.

### Configuration

Add timing parameters to your cover devices in `airsend.yaml`:

```yaml
volet cuisine:
  id: 9000
  type: 4099  # Required for position support
  apiKey: !secret apiKey
  opening_duration: 25  # Seconds to fully open
  closing_duration: 23  # Seconds to fully close
```

### Features

- **Percentage Control**: Set exact positions (0-100%) using the slider
- **Real-time Updates**: Position updates every 0.5 seconds during movement
- **State Persistence**: Position and state persist across Home Assistant restarts
- **Time-based Calculation**: Position calculated based on configured opening/closing durations
- **Automatic Stop**: Stops at target position automatically

### Usage

The cover will show a position slider in the Home Assistant UI, allowing you to:
- Set specific positions (e.g., 25%, 50%, 75%)
- Track real-time position during movement
- Stop at intermediate positions with the stop button
- See current position percentage in the UI

### Important Notes

- Type 4099 devices get full position support with slider
- Type 4098 devices work as simple open/close covers
- Position is calculated based on time, not actual feedback from the device
- Ensure `opening_duration` and `closing_duration` match your actual cover timing

### Troubleshooting

If position drift occurs over time:
1. Adjust the `opening_duration` and `closing_duration` values to better match your cover
2. Use the stop button when the cover is fully open/closed to reset the position
3. Restart Home Assistant to restore saved positions

## Preview

<img src="https://raw.githubusercontent.com/devmel/hass_airsend/master/img/screenshot.png" height="200"/>
