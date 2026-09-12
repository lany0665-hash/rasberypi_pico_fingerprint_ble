import json
import unittest

from ble_service import FingerprintBLE, advertising_payload


class FakeBLE:
    def __init__(self):
        self.notifications = []

    def active(self, value):
        self.active_value = value

    def gatts_register_services(self, services):
        return ((10, 11),)

    def irq(self, callback):
        self.callback = callback

    def gap_advertise(self, interval, adv_data):
        self.advertisement = (interval, adv_data)

    def gatts_notify(self, connection, handle, data):
        self.notifications.append((connection, handle, data))


class FakeSensor:
    def __init__(self):
        self.calls = []

    def verify_password(self):
        self.calls.append("verify")

    def capture_image(self):
        self.calls.append("capture")

    def image_to_template(self, buffer_id):
        self.calls.append(("convert", buffer_id))

    def create_model(self):
        self.calls.append("create")

    def store_model(self, template_id, buffer_id):
        self.calls.append(("store", template_id, buffer_id))


class BLEEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.ble = FakeBLE()
        self.sensor = FakeSensor()
        self.events = []
        self.controller = FingerprintBLE(
            self.sensor,
            "Test",
            ble=self.ble,
            event_callback=self.events.append,
        )

    def test_two_scan_enrollment_only_stores_after_second_next(self):
        self.controller.process_command("VERIFY")
        self.controller.process_command("ENROLL 12")
        self.controller.process_command("NEXT")

        self.assertEqual(self.controller.state, FingerprintBLE.WAIT_SECOND)
        self.assertNotIn(("store", 12, 1), self.sensor.calls)

        self.controller.process_command("NEXT")

        self.assertEqual(self.controller.state, FingerprintBLE.IDLE)
        self.assertIn(("store", 12, 1), self.sensor.calls)
        self.assertEqual(self.events[-1]["event"], "enroll_complete")

    def test_out_of_range_id_never_starts_enrollment(self):
        self.controller.process_command("VERIFY")
        self.controller.process_command("ENROLL 1000")

        self.assertEqual(self.controller.state, FingerprintBLE.IDLE)
        self.assertEqual(self.events[-1]["event"], "command_error")

    def test_advertising_name_cannot_exceed_legacy_payload(self):
        with self.assertRaises(ValueError):
            advertising_payload("x" * 27)


if __name__ == "__main__":
    unittest.main()
