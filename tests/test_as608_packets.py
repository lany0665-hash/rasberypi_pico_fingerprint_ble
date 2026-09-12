import unittest

from as608 import ACK_PACKET, AS608, AS608ProtocolError, COMMAND_PACKET


class FakeUART:
    def __init__(self, incoming=b""):
        self.incoming = bytearray(incoming)
        self.written = bytearray()

    def any(self):
        return len(self.incoming)

    def read(self, count):
        result = self.incoming[:count]
        del self.incoming[:count]
        return bytes(result)

    def write(self, data):
        self.written.extend(data)
        return len(data)


class AS608PacketTests(unittest.TestCase):
    def test_command_encodes_address_length_and_checksum(self):
        uart = FakeUART()
        sensor = AS608(uart, address=0xFFFFFFFF)

        packet = sensor._make_packet(COMMAND_PACKET, b"\x13\x00\x00\x00\x00")

        self.assertEqual(packet[:6], b"\xef\x01\xff\xff\xff\xff")
        self.assertEqual(packet[6:9], b"\x01\x00\x07")
        self.assertEqual(packet[-2:], b"\x00\x1b")

    def test_command_returns_ack_data_after_validated_packet(self):
        encoder = AS608(FakeUART())
        ack = encoder._make_packet(ACK_PACKET, b"\x00\x00\x2a")
        uart = FakeUART(ack)
        sensor = AS608(uart)

        result = sensor.command(0x1D)

        self.assertEqual(result, b"\x00\x2a")
        self.assertEqual(uart.written[6], COMMAND_PACKET)

    def test_invalid_ack_checksum_is_rejected(self):
        encoder = AS608(FakeUART())
        malformed = bytearray(encoder._make_packet(ACK_PACKET, b"\x00"))
        malformed[-1] ^= 0x01
        sensor = AS608(FakeUART(bytes(malformed)))

        with self.assertRaises(AS608ProtocolError):
            sensor.command(0x01)


if __name__ == "__main__":
    unittest.main()
