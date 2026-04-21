"""Constants for OBD2 Ducato integration."""

DOMAIN = "obd2_ducato"
DEFAULT_NAME = "OBD2 Ducato"
SCAN_INTERVAL = 5  # seconds

CONF_MAC_ADDRESS = "mac_address"
CONF_RFCOMM_PORT = "rfcomm_port"
CONF_RFCOMM_CHANNEL = "rfcomm_channel"

DEFAULT_RFCOMM_PORT = 0
DEFAULT_RFCOMM_CHANNEL = 1

ATTR_SENSOR_ID = "sensor_id"

# Standard OBD2 PIDs
SENSORS = {
    "speed": {
        "name": "Vehicle Speed",
        "icon": "mdi:speedometer",
        "unit": "km/h",
        "device_class": "speed",
        "state_class": "measurement",
        "obd_command": "SPEED",
        "custom_pid": None,
    },
    "rpm": {
        "name": "Engine RPM",
        "icon": "mdi:engine",
        "unit": "rpm",
        "device_class": None,
        "state_class": "measurement",
        "obd_command": "RPM",
        "custom_pid": None,
    },
    "coolant_temp": {
        "name": "Coolant Temperature",
        "icon": "mdi:thermometer",
        "unit": "°C",
        "device_class": "temperature",
        "state_class": "measurement",
        "obd_command": "COOLANT_TEMP",
        "custom_pid": None,
    },
    "intake_temp": {
        "name": "Intake Air Temperature",
        "icon": "mdi:thermometer",
        "unit": "°C",
        "device_class": "temperature",
        "state_class": "measurement",
        "obd_command": "INTAKE_TEMP",
        "custom_pid": None,
    },
    "engine_load": {
        "name": "Engine Load",
        "icon": "mdi:gauge",
        "unit": "%",
        "device_class": None,
        "state_class": "measurement",
        "obd_command": "ENGINE_LOAD",
        "custom_pid": None,
    },
    "throttle_pos": {
        "name": "Throttle Position",
        "icon": "mdi:gauge",
        "unit": "%",
        "device_class": None,
        "state_class": "measurement",
        "obd_command": "THROTTLE_POS",
        "custom_pid": None,
    },
    "fuel_level": {
        "name": "Fuel Level",
        "icon": "mdi:fuel",
        "unit": "%",
        "device_class": None,
        "state_class": "measurement",
        "obd_command": "FUEL_LEVEL",
        "custom_pid": None,
    },
    "maf": {
        "name": "Mass Air Flow",
        "icon": "mdi:air-filter",
        "unit": "g/s",
        "device_class": None,
        "state_class": "measurement",
        "obd_command": "MAF",
        "custom_pid": None,
    },
    "battery_voltage": {
        "name": "Battery Voltage",
        "icon": "mdi:battery",
        "unit": "V",
        "device_class": "voltage",
        "state_class": "measurement",
        "obd_command": "ELM_VOLTAGE",
        "custom_pid": None,
    },
    "run_time": {
        "name": "Engine Run Time",
        "icon": "mdi:timer",
        "unit": "s",
        "device_class": "duration",
        "state_class": "measurement",
        "obd_command": "RUN_TIME",
        "custom_pid": None,
    },
    "distance_w_mil": {
        "name": "Distance With MIL",
        "icon": "mdi:map-marker-distance",
        "unit": "km",
        "device_class": None,
        "state_class": "total_increasing",
        "obd_command": "DISTANCE_W_MIL",
        "custom_pid": None,
    },
    "fuel_consumption": {
        "name": "Fuel Consumption (estimated)",
        "icon": "mdi:gas-station",
        "unit": "L/100km",
        "device_class": None,
        "state_class": "measurement",
        "obd_command": None,  # Calculated from MAF
        "custom_pid": None,
    },
}

# Fiat Ducato 2.3 JTD specific PIDs (mode 22)
# These are known custom PIDs for the Fiat/PSA group
DUCATO_CUSTOM_PIDS = {
    "odometer": {
        "name": "Odometer",
        "icon": "mdi:counter",
        "unit": "km",
        "device_class": None,
        "state_class": "total_increasing",
        "obd_command": None,
        "custom_pid": {
            "mode": "22",
            "pid": "F40A",
            "bytes": 4,
            "formula": lambda data: int.from_bytes(data[:4], "big") / 10,
        },
    },
}
