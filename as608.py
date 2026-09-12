"""AS608 UART packet protocol driver for MicroPython."""

try:
    import utime as _time

    def _ticks_ms():
        return _time.ticks_ms()

    def _ticks_diff(now, then):
        return _time.ticks_diff(now, then)

    def _sleep_ms(milliseconds):
        _time.sleep_ms(milliseconds)
except ImportError:
    import time as _time

    def _ticks_ms():
        return int(_time.monotonic() * 1000)

    def _ticks_diff(now, then):
        return now - then

    def _sleep_ms(milliseconds):
        _time.sleep(milliseconds / 1000)


PACKET_HEADER = b"\xEF\x01"
COMMAND_PACKET = 0x01
DATA_PACKET = 0x02
ACK_PACKET = 0x07
END_DATA_PACKET = 0x08

INSTRUCTION_GET_IMAGE = 0x01
INSTRUCTION_IMAGE_TO_TEMPLATE = 0x02
INSTRUCTION_SEARCH = 0x04
INSTRUCTION_REG_MODEL = 0x05
INSTRUCTION_STORE = 0x06
INSTRUCTION_DELETE = 0x0C
INSTRUCTION_VERIFY_PASSWORD = 0x13
INSTRUCTION_TEMPLATE_COUNT = 0x1D

CONFIRMATION_MESSAGES = {
    0x01: "Packet receive error",
    0x02: "No finger detected",
    0x03: "Image enrollment failed",
    0x06: "Image is too messy",
    0x07: "Feature generation failed",
    0x09: "No matching template found",
    0x0A: "Template combine failed",
    0x0B: "Address out of range",
    0x0C: "Template read error",
    0x10: "Delete template failed",
    0x11: "Database clear failed",
    0x13: "Password verification failed",
    0x15: "Invalid image",
    0x18: "Flash write error",
    0x19: "Invalid register",
    0x1A: "Invalid configuration",
    0x1B: "Notepad error",
    0x1C: "Invalid command",
    0x1D: "Communication port error",
}


class AS608Error(Exception):
    """Base class for sensor communication and command errors."""


class AS608ProtocolError(AS608Error):
    """Malformed, incomplete, or invalid packet from the sensor."""


class AS608TimeoutError(AS608Error):
    """Sensor did not reply before the configured timeout."""


class AS608TransportError(AS608Error):
    """UART transport could not communicate with the sensor."""


class AS608CommandError(AS608Error):
    """Sensor rejected a valid command."""

    def __init__(self, code, instruction=None):
        self.code = code
        self.instruction = instruction
        message = CONFIRMATION_MESSAGES.get(code, "Sensor error 0x%02X" % code)
        AS608Error.__init__(self, message)


def _u16(value):
    return bytes(((value >> 8) & 0xFF, value & 0xFF))


def _u32(value):
    return bytes((
        (value >> 24) & 0xFF,
        (value >> 16) & 0xFF,
        (value >> 8) & 0xFF,
        value & 0xFF,
    ))


def _read_u16(value):
    return (value[0] << 8) | value[1]


class AS608:
    """Driver for the standard AS608 command packet protocol."""

    def __init__(self, uart, address=0xFFFFFFFF, password=0,
                 timeout_ms=1500, max_packet_length=512):
        self.uart = uart
        self.address = address
        self.password = password
        self.timeout_ms = timeout_ms
        self.max_packet_length = max_packet_length

    def _make_packet(self, packet_type, payload):
        if len(payload) > self.max_packet_length - 2:
            raise ValueError("AS608 payload exceeds configured packet length")
        length = len(payload) + 2
        body = bytes((packet_type,)) + _u16(length) + payload
        checksum = sum(body) & 0xFFFF
        return PACKET_HEADER + _u32(self.address) + body + _u16(checksum)

    def _read_exact(self, count, timeout_ms=None):
        timeout_ms = self.timeout_ms if timeout_ms is None else timeout_ms
        deadline = _ticks_ms()
        data = bytearray()
        while len(data) < count:
            try:
                available = self.uart.any()
            except OSError as error:
                raise AS608TransportError("AS608 UART availability check failed: %s" % error)
            if available:
                try:
                    chunk = self.uart.read(min(available, count - len(data)))
                except OSError as error:
                    raise AS608TransportError("AS608 UART read failed: %s" % error)
                if chunk:
                    data.extend(chunk)
                    continue
            if _ticks_diff(_ticks_ms(), deadline) >= timeout_ms:
                raise AS608TimeoutError(
                    "Timed out waiting for %d AS608 packet bytes" % (count - len(data))
                )
            _sleep_ms(2)
        return bytes(data)

    def _read_packet(self):
        header = self._read_exact(9)
        if header[:2] != PACKET_HEADER:
            raise AS608ProtocolError("AS608 packet header is invalid")
        address = ((header[2] << 24) | (header[3] << 16) |
                   (header[4] << 8) | header[5])
        if address != self.address:
            raise AS608ProtocolError("AS608 packet address does not match")
        packet_type = header[6]
        length = _read_u16(header[7:9])
        if length < 2 or length > self.max_packet_length:
            raise AS608ProtocolError("AS608 packet length is invalid: %d" % length)
        payload_and_checksum = self._read_exact(length)
        payload = payload_and_checksum[:-2]
        received_checksum = _read_u16(payload_and_checksum[-2:])
        calculated_checksum = sum(header[6:] + payload) & 0xFFFF
        if received_checksum != calculated_checksum:
            raise AS608ProtocolError("AS608 packet checksum does not match")
        return packet_type, payload

    def command(self, instruction, parameters=b""):
        """Send a command and return ACK payload bytes after confirmation byte."""
        packet = self._make_packet(COMMAND_PACKET, bytes((instruction,)) + parameters)
        try:
            written = self.uart.write(packet)
        except OSError as error:
            raise AS608TransportError("AS608 UART write failed: %s" % error)
        if written is not None and written != len(packet):
            raise AS608TransportError(
                "AS608 UART wrote %d of %d packet bytes" % (written, len(packet))
            )
        packet_type, payload = self._read_packet()
        if packet_type != ACK_PACKET:
            raise AS608ProtocolError(
                "Expected AS608 ACK packet, received 0x%02X" % packet_type
            )
        if not payload:
            raise AS608ProtocolError("AS608 ACK packet lacks confirmation code")
        if payload[0] != 0:
            raise AS608CommandError(payload[0], instruction)
        return payload[1:]

    def verify_password(self, password=None):
        self.command(
            INSTRUCTION_VERIFY_PASSWORD,
            _u32(self.password if password is None else password),
        )
        return True

    def capture_image(self):
        self.command(INSTRUCTION_GET_IMAGE)
        return True

    def image_to_template(self, buffer_id=1):
        if buffer_id not in (1, 2):
            raise ValueError("AS608 template buffer must be 1 or 2")
        self.command(INSTRUCTION_IMAGE_TO_TEMPLATE, bytes((buffer_id,)))
        return True

    def create_model(self):
        self.command(INSTRUCTION_REG_MODEL)
        return True

    def store_model(self, template_id, buffer_id=1):
        self._validate_template_id(template_id)
        if buffer_id not in (1, 2):
            raise ValueError("AS608 template buffer must be 1 or 2")
        self.command(
            INSTRUCTION_STORE,
            bytes((buffer_id,)) + _u16(template_id),
        )
        return True

    def search(self, buffer_id=1, start_id=0, count=1000):
        self._validate_template_id(start_id)
        if buffer_id not in (1, 2):
            raise ValueError("AS608 template buffer must be 1 or 2")
        if not 1 <= count <= 0xFFFF:
            raise ValueError("AS608 search count must be between 1 and 65535")
        result = self.command(
            INSTRUCTION_SEARCH,
            bytes((buffer_id,)) + _u16(start_id) + _u16(count),
        )
        if len(result) != 4:
            raise AS608ProtocolError("AS608 search response has invalid length")
        return _read_u16(result[:2]), _read_u16(result[2:])

    def delete_model(self, template_id, count=1):
        self._validate_template_id(template_id)
        if not 1 <= count <= 0xFFFF:
            raise ValueError("AS608 delete count must be between 1 and 65535")
        self.command(INSTRUCTION_DELETE, _u16(template_id) + _u16(count))
        return True

    def template_count(self):
        result = self.command(INSTRUCTION_TEMPLATE_COUNT)
        if len(result) != 2:
            raise AS608ProtocolError("AS608 template count response has invalid length")
        return _read_u16(result)

    @staticmethod
    def _validate_template_id(template_id):
        if not 0 <= template_id <= 0xFFFF:
            raise ValueError("AS608 template ID must be between 0 and 65535")
