"""Device entry point. Upload this file and its sibling modules to the Pico W."""

from machine import Pin, UART
import time

import config
from as608 import AS608
from ble_service import FingerprintBLE
from firebase import FirebaseError, FirebaseReporter
from wifi import WiFiError, WiFiManager


def run():
    uart = UART(
        config.AS608_UART_ID,
        baudrate=config.AS608_BAUDRATE,
        tx=Pin(config.AS608_TX_PIN),
        rx=Pin(config.AS608_RX_PIN),
    )
    sensor = AS608(
        uart,
        address=config.AS608_ADDRESS,
        password=config.AS608_PASSWORD,
        timeout_ms=config.AS608_TIMEOUT_MS,
    )
    wifi = WiFiManager(
        config.WIFI_SSID,
        config.WIFI_PASSWORD,
        config.WIFI_CONNECT_TIMEOUT_MS,
    )
    firebase = FirebaseReporter(
        config.FIREBASE_DATABASE_URL,
        config.FIREBASE_AUTH_TOKEN,
        config.FIREBASE_DEVICE_ID,
        config.FIREBASE_CA_CERTIFICATE,
        config.FIREBASE_TIMEOUT_S,
    )

    ble = None
    reporting_enabled = [False]

    def report_event(event):
        if not reporting_enabled[0]:
            return
        try:
            firebase.report(event)
        except FirebaseError as error:
            ble.publish_diagnostic("firebase_error", message=str(error))

    ble = FingerprintBLE(
        sensor,
        config.BLE_DEVICE_NAME,
        config.TEMPLATE_ID_MIN,
        config.TEMPLATE_ID_MAX,
        event_callback=report_event,
    )

    if firebase.partially_configured:
        if not firebase.configured:
            ble.publish_diagnostic(
                "firebase_error",
                message="Firebase needs URL, auth token, device ID, and CA certificate",
            )
        if not wifi.configured:
            ble.publish_diagnostic(
                "firebase_error",
                message="Firebase is configured but Wi-Fi credentials are missing",
            )
        elif firebase.configured:
            try:
                wifi.connect()
                wifi.sync_time()
                reporting_enabled[0] = True
                ble.publish_diagnostic("wifi_connected")
            except WiFiError as error:
                ble.publish_diagnostic("wifi_error", message=str(error))

    while True:
        ble.poll()
        time.sleep_ms(20)


if __name__ == "__main__":
    run()
