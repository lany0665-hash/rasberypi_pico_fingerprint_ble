"""BLE GATT control endpoint and safe enrollment state machine."""

try:
    import bluetooth
except ImportError:
    bluetooth = None

try:
    import ujson as json
except ImportError:
    import json

from as608 import AS608CommandError, AS608Error

SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
CONTROL_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
EVENT_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

_IRQ_CENTRAL_CONNECT = 1
_IRQ_CENTRAL_DISCONNECT = 2
_IRQ_GATTS_WRITE = 3
_FLAG_WRITE = 0x0008
_FLAG_WRITE_NO_RESPONSE = 0x0004
_FLAG_NOTIFY = 0x0010
_ADV_TYPE_FLAGS = 0x01
_ADV_TYPE_NAME = 0x09


def advertising_payload(name):
    encoded_name = name.encode("utf-8")
    if len(encoded_name) > 26:
        raise ValueError("BLE advertised name is too long")
    return bytes((2, _ADV_TYPE_FLAGS, 0x06, len(encoded_name) + 1, _ADV_TYPE_NAME)) + encoded_name


class FingerprintBLE:
    """Processes small BLE commands outside IRQ context and emits JSON events."""

    IDLE = "idle"
    WAIT_FIRST = "wait_first"
    WAIT_SECOND = "wait_second"
    MAX_PENDING_COMMANDS = 4

    def __init__(self, sensor, name, template_id_min=0, template_id_max=999,
                 ble=None, event_callback=None):
        if template_id_min < 0 or template_id_max > 0xFFFF:
            raise ValueError("Template bounds must fit AS608 IDs")
        if template_id_min > template_id_max:
            raise ValueError("Template ID minimum must not exceed maximum")
        if ble is None:
            if bluetooth is None:
                raise RuntimeError("MicroPython bluetooth module is required")
            ble = bluetooth.BLE()
        self.sensor = sensor
        self.ble = ble
        self.name = name
        self.template_id_min = template_id_min
        self.template_id_max = template_id_max
        self.event_callback = event_callback
        self.state = self.IDLE
        self.pending_id = None
        self.verified = False
        self._connections = set()
        self._pending_commands = []
        self._command_overflow = False

        self.ble.active(True)
        service = (
            bluetooth.UUID(SERVICE_UUID) if bluetooth else SERVICE_UUID,
            (
                (
                    bluetooth.UUID(CONTROL_UUID) if bluetooth else CONTROL_UUID,
                    _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE,
                ),
                (
                    bluetooth.UUID(EVENT_UUID) if bluetooth else EVENT_UUID,
                    _FLAG_NOTIFY,
                ),
            ),
        )
        handles = self.ble.gatts_register_services((service,))
        self.control_handle, self.event_handle = handles[0]
        self.ble.irq(self._irq)
        self._advertise()

    def _advertise(self):
        self.ble.gap_advertise(250000, adv_data=advertising_payload(self.name))

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            self._connections.add(data[0])
        elif event == _IRQ_CENTRAL_DISCONNECT:
            self._connections.discard(data[0])
            self._advertise()
        elif event == _IRQ_GATTS_WRITE and data[1] == self.control_handle:
            if len(self._pending_commands) >= self.MAX_PENDING_COMMANDS:
                self._command_overflow = True
                return
            raw = self.ble.gatts_read(self.control_handle)
            if len(raw) > 64:
                self._pending_commands.append(None)
            else:
                self._pending_commands.append(raw)

    def poll(self):
        """Process queued commands. Call this regularly from the main loop."""
        if self._command_overflow:
            self._command_overflow = False
            self._emit("command_error", message="Command queue is full; command dropped")
        while self._pending_commands:
            raw = self._pending_commands.pop(0)
            if raw is None:
                self._emit("command_error", message="Command exceeds 64 bytes")
                continue
            try:
                command = raw.decode("ascii").strip()
            except UnicodeError:
                self._emit("command_error", message="Command must be ASCII")
                continue
            self.process_command(command)

    def process_command(self, command):
        """Public for testability; command execution always occurs outside IRQ."""
        parts = command.upper().split()
        if not parts:
            self._emit("command_error", message="Command is empty")
            return
        operation = parts[0]
        try:
            if operation == "STATUS" and len(parts) == 1:
                self._emit("status", verified=self.verified)
            elif operation == "VERIFY" and len(parts) == 1:
                self._verify()
            elif operation == "ENROLL" and len(parts) == 2:
                self._start_enrollment(self._parse_template_id(parts[1]))
            elif operation == "NEXT" and len(parts) == 1:
                self._advance_enrollment()
            elif operation == "CANCEL" and len(parts) == 1:
                self._cancel_enrollment()
            elif operation == "IDENTIFY" and len(parts) == 1:
                self._identify()
            elif operation == "DELETE" and len(parts) == 2:
                self._delete(self._parse_template_id(parts[1]))
            elif operation == "COUNT" and len(parts) == 1:
                self._count()
            else:
                self._emit("command_error", message="Invalid command syntax")
        except ValueError as error:
            self._emit("command_error", message=str(error))
        except AS608CommandError as error:
            self._emit("sensor_error", code=error.code, message=str(error))
        except AS608Error as error:
            self._emit("sensor_error", message=str(error))

    def _verify(self):
        self.sensor.verify_password()
        self.verified = True
        self._emit("verified", message="AS608 password verified")

    def _require_verified(self):
        if not self.verified:
            raise ValueError("Send VERIFY successfully before sensor operations")

    def _parse_template_id(self, value):
        if not value.isdigit():
            raise ValueError("Template ID must be a decimal integer")
        template_id = int(value)
        if not self.template_id_min <= template_id <= self.template_id_max:
            raise ValueError(
                "Template ID must be between %d and %d" %
                (self.template_id_min, self.template_id_max)
            )
        return template_id

    def _start_enrollment(self, template_id):
        self._require_verified()
        if self.state != self.IDLE:
            raise ValueError("Enrollment already in progress; send CANCEL or NEXT")
        self.pending_id = template_id
        self.state = self.WAIT_FIRST
        self._emit(
            "enroll_started",
            id=template_id,
            message="Place finger for first scan, then send NEXT.",
        )

    def _advance_enrollment(self):
        self._require_verified()
        if self.state == self.WAIT_FIRST:
            self.sensor.capture_image()
            self.sensor.image_to_template(1)
            self.state = self.WAIT_SECOND
            self._emit(
                "enroll_first_captured",
                id=self.pending_id,
                message="Remove and place the same finger again, then send NEXT.",
            )
        elif self.state == self.WAIT_SECOND:
            self.sensor.capture_image()
            self.sensor.image_to_template(2)
            self.sensor.create_model()
            self.sensor.store_model(self.pending_id, 1)
            template_id = self.pending_id
            self._clear_enrollment()
            self._emit("enroll_complete", id=template_id)
        else:
            raise ValueError("No enrollment is waiting for a scan")

    def _cancel_enrollment(self):
        if self.state == self.IDLE:
            self._emit("status", message="No enrollment in progress", verified=self.verified)
            return
        template_id = self.pending_id
        self._clear_enrollment()
        self._emit("enroll_cancelled", id=template_id)

    def _clear_enrollment(self):
        self.state = self.IDLE
        self.pending_id = None

    def _identify(self):
        self._require_verified()
        if self.state != self.IDLE:
            raise ValueError("Cancel or complete enrollment before identifying")
        self.sensor.capture_image()
        self.sensor.image_to_template(1)
        try:
            template_id, score = self.sensor.search(
                1, self.template_id_min,
                self.template_id_max - self.template_id_min + 1,
            )
            self._emit("match", id=template_id, score=score)
        except AS608CommandError as error:
            if error.code == 0x09:
                self._emit("no_match", message=str(error))
            else:
                raise

    def _delete(self, template_id):
        self._require_verified()
        if self.state != self.IDLE:
            raise ValueError("Cancel or complete enrollment before deleting")
        self.sensor.delete_model(template_id)
        self._emit("template_deleted", id=template_id)

    def _count(self):
        self._require_verified()
        count = self.sensor.template_count()
        self._emit("template_count", count=count)

    def _emit(self, event, **fields):
        payload = {"event": event, "state": self.state}
        payload.update(fields)
        message = json.dumps(payload)
        self._notify(message.encode("utf-8"))
        if self.event_callback:
            self.event_callback(payload)

    def publish_diagnostic(self, event, **fields):
        """Notify an event without feeding it back into external reporting."""
        payload = {"event": event, "state": self.state}
        payload.update(fields)
        self._notify(json.dumps(payload).encode("utf-8"))

    def _notify(self, data):
        for connection in self._connections:
            self.ble.gatts_notify(connection, self.event_handle, data)
