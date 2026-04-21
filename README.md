# OBD2 Ducato - Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for reading OBD2 data from a **Fiat Ducato 2.3 JTD** (and similar diesel vehicles) via a Bluetooth ELM327 adapter (tested with KONNWEI KW905 Bluetooth 5.0).

## Features

- 🔵 **Automatic Bluetooth pairing** — no manual `bluetoothctl` needed
- 🔄 **Auto-reconnect** — if the adapter disconnects it will re-bind
- 🚗 **Sensor auto-detection** — only creates entities for sensors your vehicle supports
- 🛢️ **Ducato-specific PIDs** — attempts odometer via Fiat custom PIDs
- 📊 **Estimated fuel consumption** — calculated from MAF sensor (L/100km)

## Supported Sensors

| Sensor | Type | Notes |
|--------|------|-------|
| Vehicle Speed | km/h | Standard OBD2 |
| Engine RPM | rpm | Standard OBD2 |
| Coolant Temperature | °C | Standard OBD2 |
| Intake Air Temperature | °C | Standard OBD2 |
| Engine Load | % | Standard OBD2 |
| Throttle Position | % | Standard OBD2 |
| Fuel Level | % | May not be available on all Ducatos |
| Battery Voltage | V | Via ELM327 AT RV command |
| Mass Air Flow | g/s | Standard OBD2 |
| Engine Run Time | s | Standard OBD2 |
| Fuel Consumption (est.) | L/100km | Calculated from MAF + speed |
| Odometer | km | Fiat custom PID (may not work on all years) |

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the three dots menu → **Custom repositories**
4. Add `https://github.com/oskarhart/obd2_ducato` as an **Integration**
5. Install **OBD2 Ducato**
6. Restart Home Assistant

### Manual

1. Copy the `custom_components/obd2_ducato` folder to your HA `custom_components` directory
2. Restart Home Assistant

## Setup

1. Plug the OBD2 adapter into your vehicle's OBD2 port
2. Start the engine (recommended for first setup)
3. In HA go to **Settings → Integrations → Add Integration**
4. Search for **OBD2 Ducato**
5. Enter the Bluetooth MAC address of your adapter
6. The integration will scan, pair, and connect automatically

## Finding Your Adapter's MAC Address

You can find the MAC address by:
- Checking the label on the adapter
- Using a Bluetooth scanner app on your phone (e.g. "BLE Scanner")
- The setup form will scan and show nearby devices automatically

## Hardware Tested

- **Vehicle:** Fiat Ducato 2.3 JTD (2008)
- **Adapter:** KONNWEI KW905 Bluetooth 5.0
- **HA Host:** Raspberry Pi 5 running HA OS

## Troubleshooting

**No sensors appear:**
- Make sure the engine is running during first setup
- Check HA logs for OBD2 connection errors
- Verify the adapter LED is on/blinking

**Bluetooth pairing fails:**
- Make sure the vehicle is within Bluetooth range
- Try restarting the integration
- Check that no other device is connected to the adapter (ELM327 typically only allows one connection at a time)

**Odometer not available:**
- The Fiat custom PID for odometer is not guaranteed on all Ducato variants/years

## License

MIT
