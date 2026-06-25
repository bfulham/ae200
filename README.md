# Mitsubishi AE-200 for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/bfulham/ae200)](https://github.com/bfulham/ae200/releases)
[![HACS Validation](https://github.com/bfulham/ae200/actions/workflows/validate.yml/badge.svg)](https://github.com/bfulham/ae200/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/bfulham/ae200)](https://github.com/bfulham/ae200/blob/main/LICENSE)
[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bfulham&repository=ae200&category=integration)

A local Home Assistant integration for Mitsubishi Electric AE-200
air-conditioning controllers.

It discovers every configured AE-200 group, represents each group as a climate
device, polls all groups in a single request and verifies control changes by
reading back only the selected group.

> **Version 1.1.0**

## Highlights

- Local polling through the controller's `/b_xmlproc/` WebSocket endpoint
- UI configuration and reconfiguration
- One Home Assistant device and climate entity per AE-200 group
- Batched polling for all groups
- Heat, Cool, Auto, power, temperature, fan and air-direction controls
- Correct automatic-mode handling:
  - Sends `Mode="AUTO"`
  - Accepts `AUTOCOOL` and `AUTOHEAT` as Auto read-back states
  - Infers heating or cooling action from the reported state
- Exact single-group writes with configurable read-back verification
- Retry and cached-state grace handling for intermittent controller dropouts
- Automatic group rediscovery
- Diagnostics with the controller address redacted
- Legacy YAML import from the older `ae200` custom component

## Requirements

- Home Assistant **2025.1.0 or newer**
- HACS, for HACS installation
- Network access from Home Assistant to the AE-200 controller
- No cloud account or Internet access is required for controller operation

The controller should remain on a trusted local network. The integration uses
unencrypted local WebSocket traffic because that is what the AE-200 endpoint
provides.

## Installation

### HACS custom repository

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and select **Custom repositories**.
3. Add:

   ```text
   https://github.com/bfulham/ae200
   ```

4. Select **Integration** as the category.
5. Open **Mitsubishi AE-200** in HACS and select **Download**.
6. Restart Home Assistant.
7. Open **Settings → Devices & services → Add integration**.
8. Search for **Mitsubishi AE-200**.
9. Enter the controller IP address or hostname.

### Manual installation

1. Download the latest release.
2. Copy:

   ```text
   custom_components/ae200
   ```

   to:

   ```text
   /config/custom_components/ae200
   ```

3. Restart Home Assistant.
4. Add **Mitsubishi AE-200** from **Settings → Devices & services**.

## Upgrading

HACS manages upgrades automatically after the repository is installed. Restart
Home Assistant after installing an update.

For a manual upgrade, replace `/config/custom_components/ae200` with the folder
from the new release and restart Home Assistant.

## Migrating from the original integration

The old YAML format can be imported:

```yaml
climate:
  - platform: ae200
    controller_id: main_controller
    ip_address: 192.168.1.10
```

Leave the YAML in place for the first restart. When the controller appears under
**Settings → Devices & services**, remove that YAML block and restart again.

The new integration uses stable unique IDs based on the config entry and AE-200
group ID. Existing dashboards may need their old entity IDs changed to the new
entity IDs after migration.

## Climate controls

Each group supports:

| Home Assistant control | AE-200 value |
|---|---|
| Off | `Drive="OFF"` |
| On | `Drive="ON"` |
| Heat | `Mode="HEAT"` |
| Cool | `Mode="COOL"` |
| Auto | `Mode="AUTO"` |
| Target temperature | `SetTemp="<temperature>"` |
| Fan | `FanSpeed="AUTO/LOW/MID1/MID2/HIGH"` |
| Air direction | `AirDirection="HORIZONTAL/VERTICAL/SWING"` |

`AUTOCOOL` and `AUTOHEAT` are controller status values. They are both shown as
Home Assistant's **Auto** mode, while the HVAC action indicates whether Auto is
currently cooling or heating.

Dry and Fan-only can be exposed through integration options, but are disabled by
default because they were not observed in the supplied controller capture.

## Additional entities

Enabled by default:

- Error
- Filter service required
- Check water
- Configured group count
- Running group count
- Fault count
- Filter-alert count
- Scheduled-group count
- Rediscover and refresh button

Available but disabled by default:

- Separate room and target temperature sensors
- Humidity and outdoor temperature
- Raw operating mode
- Fan speed and air direction
- Schedule, hold and energy-control status
- Remote-control and mode-control permission
- Schedule availability
- Groups using cached data

Enable these from the relevant device's **Entities** page.

## Resilience options

The defaults are designed to avoid all aircons becoming unavailable after one
brief WebSocket failure:

| Option | Default |
|---|---:|
| Polling interval | 30 seconds |
| Connection timeout | 10 seconds |
| Retries after a failed poll | 2 |
| Initial retry delay | 0.75 seconds |
| Failed polls tolerated before unavailable | 3 |

During the grace period, climate entities keep their last successful state and
expose `data_stale: true`. The controller diagnostic sensor **Groups using
cached data** shows how many groups are using cached values.

## Diagnostics and troubleshooting

Open **Settings → Devices & services → Mitsubishi AE-200**, select the
three-dot menu and choose **Download diagnostics**.

The diagnostics include:

- Discovered groups
- Cached raw attributes
- Protocol warnings
- Consecutive poll failures
- Last poll and write errors
- Groups using cached data

The configured controller address is redacted. Review group names and other
returned controller data before sharing a diagnostics file publicly.

### Integration cannot be added

- Confirm Home Assistant can reach the controller IP.
- Confirm TCP access to the controller's HTTP/WebSocket service is not blocked.
- Remove any old duplicate `custom_components/ae200` folder and restart.
- Clear the browser cache if the integration does not appear after installation.

### All entities become unavailable

- Increase the timeout or polling interval under **Configure**.
- Download diagnostics immediately after the event.
- Check Home Assistant logs for `custom_components.ae200`.
- Confirm the controller is not being heavily polled by several systems at once.

### A write is not confirmed

The integration deliberately reports failure when the selected group does not
read back the requested value. Some indoor-unit types may reject unsupported
mode, fan or vane settings even if the AE-200 accepts the request.

## Removing the integration

1. Remove the Mitsubishi AE-200 config entry from **Settings → Devices &
   services**.
2. Remove the repository from HACS.
3. Restart Home Assistant.
4. Remove any remaining legacy YAML configuration.

## Supported controller data

The implementation was developed using a read-only capture from a real AE-200
with 42 groups. Confirmed values include:

- `Drive`: `ON`, `OFF`
- `Mode`: `HEAT`, `COOL`, `AUTOCOOL`, plus confirmed `AUTOHEAT`
- `ModeStatus`: `ENABLE`
- `FanSpeed`: `AUTO`, `LOW`, `MID1`, `MID2`, `HIGH`
- `AirDirection`: `HORIZONTAL`, `VERTICAL`, `SWING`
- `FilterSign`: `ON`, `OFF`
- `Schedule`: `ON`, `OFF`
- `RemoCon`: `PERMIT`

The integration excludes attributes that this controller returned as
`Unknown Attribute (0101)`.

## Contributing and support

- [Report a bug](https://github.com/bfulham/ae200/issues/new/choose)
- [Request a feature](https://github.com/bfulham/ae200/issues/new/choose)
- [Contributing guide](https://github.com/bfulham/ae200/blob/main/CONTRIBUTING.md)
- [Security policy](https://github.com/bfulham/ae200/blob/main/SECURITY.md)

Protocol changes should be backed by a redacted, read-only controller capture
whenever possible.

## Credits

The initial WebSocket/XML behaviour was informed by
[`natevoci/ae200`](https://github.com/natevoci/ae200). This project is an
independent reimplementation informed further by real controller responses.

## Disclaimer

This is an unofficial community integration. It is not affiliated with or
endorsed by Mitsubishi Electric or the original repository's author.

## License

MIT — see [LICENSE](LICENSE).
