# Jolly Mec 4HEAT for Home Assistant

[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Control a pellet stove or insert fitted with a Tiemme Elettronica **4HEAT** Wi-Fi
module (the platform behind the **Jolly Mec Connect** app) from Home Assistant.

The 4heatlite module is cloud only: it opens no usable local port, so this
integration talks to the same Azure backend the app uses. Reads need no account;
writes use your myJOLLY MEC login.

## What you get

- A **climate** entity mirroring the stove: current room temperature, the stove
  setpoint as target temperature, and OFF / HEAT mapped to the real extinguish and
  ignition commands. `hvac_action` reflects the stove state (heating, idle in
  standby, off).
- **Sensors**: room temperature, flue temperature, status, error, and every power
  level the stove reports (combustion, heating, ducted 1, ducted 2).
- **Selects** for the stove's enumerated menu settings (combustion and heating
  power P1-P6/Auto enabled by default; ducted powers and the temperature source
  selector added disabled).
- **Numbers** for the numeric menu settings (remote room temperatures, added
  disabled).
- A **Heat demand** switch: the lever for building your own thermostat with an
  adjustable delta (see below).

## Supported devices

4HEAT modules speaking the modern **2ways** protocol (for example Jolly Mec stoves
and inserts with the 4heatlite module). Older `syevo` devices are not supported yet.
The setup will tell you if the protocol does not match.

## Install

1. Add the repository to HACS, then install "Jolly Mec 4HEAT":

   [![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=vodhash&repository=jollymec-4heat&category=integration)

   Or do it by hand: HACS > three-dot menu > Custom repositories, add
   `https://github.com/vodhash/jollymec-4heat` (category: Integration), then install it.
2. Restart Home Assistant.
3. Settings > Devices & Services > Add Integration > Jolly Mec 4HEAT.
4. Enter:
   - **Device Id** and **PIN**: from the app, myJOLLY MEC tab (default PIN `000000`).
   - **Account email / password**: your myJOLLY MEC account, needed for commands.

## Your own thermostat with an adjustable delta

The stove's native standby uses a fixed delta you cannot change. To regulate on
your own sensors with your own delta, point Home Assistant's built-in
`generic_thermostat` at the **Heat demand** switch. The switch drives the stove by
pushing its setpoint high (run) or low (native standby), so the stove never fully
shuts down between cycles.

Average two sensors (for example Tapo probes in the kitchen and the living room):

```yaml
template:
  - sensor:
      - name: Living area temperature
        unit_of_measurement: "°C"
        device_class: temperature
        state: >
          {{ ((states('sensor.kitchen_temperature') | float
              + states('sensor.living_room_temperature') | float) / 2) | round(1) }}

climate:
  - platform: generic_thermostat
    name: Stove thermostat
    heater: switch.stove_heat_demand
    target_sensor: sensor.living_area_temperature
    cold_tolerance: 0.3
    hot_tolerance: 0.3
    min_cycle_duration: "00:20:00"
```

Use either this thermostat or the stove's own climate entity, not both at once:
both drive the same setpoint.

## How it works

The full reverse-engineered protocol (endpoints, auth, frame format, register map,
commands) is documented in [PROTOCOL.md](PROTOCOL.md). A dependency-free CLI,
`jm4heat.py`, reads and prints the live state for debugging.

## Limitations

- Cloud only, polled every 60 s. State reflects the module's last report.
- The power sensors stay read only; set the powers through the Select entities.
- Hidden menu parameters (ducted powers, source selector, remote rooms) are
  exposed but disabled by default. Enable one only if you know what it does; the
  selector and remote room values change how the stove reads temperature.
- 2ways protocol only.

## Disclaimer

Unofficial, not affiliated with Tiemme Elettronica or Jolly Mec. A pellet stove is
a combustion appliance; use at your own risk and keep the required safety devices.

## License

Apache-2.0. See [LICENSE](LICENSE).
