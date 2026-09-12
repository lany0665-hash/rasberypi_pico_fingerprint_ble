"""Central device configuration. Copy credentials only into secrets.py."""

try:
    import secrets as _secrets
except ImportError:
    _secrets = None


def _secret(name, default=None):
    return getattr(_secrets, name, default) if _secrets else default


# AS608 UART configuration. Change pins/baud/address only here.
AS608_UART_ID = 0
AS608_TX_PIN = 0
AS608_RX_PIN = 1
AS608_BAUDRATE = 57600
AS608_ADDRESS = 0xFFFFFFFF
AS608_PASSWORD = 0x00000000
AS608_TIMEOUT_MS = 1500
TEMPLATE_ID_MIN = 0
TEMPLATE_ID_MAX = 999

# BLE configuration.
BLE_DEVICE_NAME = "PicoW-Fingerprint"

# Wi-Fi and Firebase are disabled unless all values are supplied in secrets.py.
WIFI_SSID = _secret("WIFI_SSID")
WIFI_PASSWORD = _secret("WIFI_PASSWORD")
FIREBASE_DATABASE_URL = _secret("FIREBASE_DATABASE_URL")
FIREBASE_AUTH_TOKEN = _secret("FIREBASE_AUTH_TOKEN")
FIREBASE_DEVICE_ID = _secret("FIREBASE_DEVICE_ID", "pico-w-01")
FIREBASE_CA_CERTIFICATE = _secret("FIREBASE_CA_CERTIFICATE")
WIFI_CONNECT_TIMEOUT_MS = 15000
FIREBASE_TIMEOUT_S = 8
