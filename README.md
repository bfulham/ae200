# Mitsubishi AE-200 for Home Assistant

**Release:** 0.1.0 hardware-test build

A modern, UI-configured Home Assistant custom integration for Mitsubishi
Electric AE-200 air-conditioning controllers.

This implementation was built from:

- The AE-200 WebSocket/XML behaviour demonstrated by `natevoci/ae200`
- A real read-only controller dump containing 42 groups
- The current Home Assistant climate entity and DataUpdateCoordinator APIs

## Major improvements over the original integration

- UI config flow instead of YAML-only setup
- One batched poll for every aircon instead of one connection per entity
- Asynchronous I/O through Home Assistant's shared `aiohttp` session
- No additional Python package installation required
- Automatic setup retry when the controller is offline
- Serialized writes so polling cannot interleave with a control sequence
- Every write targets exactly one group
- Read-back verification after changes
- Correct Auto handling:
  - Sends `Mode="AUTO"`
  - Maps `AUTOCOOL` and `AUTOHEAT` back to Home Assistant `auto`
  - Reports heating or cooling action from those states
- Correctly treats `ModeStatus="ENABLE"` as permission/status, not mode
- Avoids six attributes that the supplied controller rejected with error 0101
- Config entry and per-device diagnostics
- Automatic rediscovery of group names and newly added groups
- Host reconfiguration from the integration menu
- Legacy YAML import
- Controller and per-group devices

## Climate features

Each AE-200 group becomes a Home Assistant climate entity with:

- Power on/off
- Heat
- Cool
- Auto
- Optional Dry and Fan-only modes
- Current room temperature
- Target temperature
- 0.5 °C target steps
- Fan speed:
  - AUTO
  - LOW
  - MID1
  - MID2
  - HIGH
- Air direction:
  - HORIZONTAL
  - VERTICAL
  - SWING
- Inferred HVAC action
- Dynamic or configurable temperature limits

When Home Assistant selects Auto, the integration sends:

```xml
<Packet>
  <Command>setRequest</Command>
  <DatabaseManager>
    <Mnet Group="SELECTED_GROUP" Mode="AUTO" />
  </DatabaseManager>
</Packet>
```

If the selected group is off, it first sends `Drive="ON"` to that same group.
No other group is included.

## Additional entities

Enabled by default:

- Error problem sensor
- Filter-service problem sensor
- Check-water problem sensor
- Controller group count
- Running group count
- Fault count
- Filter alert count
- Scheduled group count
- Rediscover/refresh button

Available but disabled by default:

- Room temperature sensor
- Target temperature sensor
- Inlet humidity
- Outdoor temperature
- Raw controller mode
- Raw fan speed
- Air direction
- Schedule active
- Hold active
- Energy control active
- Remote control permitted
- Mode control enabled
- Occupancy, when the group reports it
- Schedule available

Enable disabled entities from the device's **Entities** page.

## Installation

### Manual

1. Remove or rename the old `custom_components/ae200` folder.
2. Copy this package's `custom_components/ae200` folder to:

   ```text
   /config/custom_components/ae200
   ```

3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **Mitsubishi AE-200**.
6. Enter the controller IP address or hostname.

### Existing YAML configuration

The old format is automatically imported:

```yaml
climate:
  - platform: ae200
    controller_id: main_controller
    ip_address: 192.168.1.10
```

After the integration appears under **Devices & services**, remove the old YAML
block and restart Home Assistant again.

## Options

Open the integration's **Configure** dialog to change:

- Controller address through **Reconfigure**
- Polling interval
- Network timeout
- Write verification
- Verification attempts and delay
- Fallback temperature range
- Air-direction control
- Optional Dry and Fan-only modes

Dry and Fan-only are disabled by default because neither appeared in the
supplied controller dump.

## Diagnostics

Use **Download diagnostics** from the integration or device page. The
controller host is redacted. Diagnostics include discovered groups, raw cached
attributes, protocol warnings and write verification errors.

## Controller fields confirmed by the supplied dump

Observed values included:

- `Drive`: `ON`, `OFF`
- `Mode`: `HEAT`, `COOL`, `AUTOCOOL`
- Additional confirmed automatic state: `AUTOHEAT`
- `ModeStatus`: `ENABLE`
- `FanSpeed`: `AUTO`, `LOW`, `MID1`, `MID2`, `HIGH`
- `AirDirection`: `HORIZONTAL`, `VERTICAL`, `SWING`
- `FilterSign`: `ON`, `OFF`
- `Schedule`: `ON`, `OFF`
- `RemoCon`: `PERMIT`

The following requested names returned `Unknown Attribute` and are not used:

- `DriveStatus`
- `SetTempStatus`
- `AirDirectionStatus`
- `AirDirectionItem`
- `FanSpeedStatus`
- `ErrorCode`

## Important testing note

The read path is based directly on the supplied controller dump. Control
packets follow the existing GitHub protocol and are verified by reading only
the selected group back. The supplied dump did not contain write traffic, so
first test each control type on a non-critical group.
