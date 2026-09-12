import unittest

import firebase
from firebase import FirebaseError, FirebaseReporter


class FirebaseReporterTests(unittest.TestCase):
    def test_reporter_requires_ca_certificate(self):
        reporter = FirebaseReporter(
            "https://example.firebaseio.com",
            "token",
            "device",
            None,
        )

        self.assertFalse(reporter.configured)

    def test_dns_error_becomes_firebase_error(self):
        reporter = FirebaseReporter(
            "https://example.firebaseio.com",
            "token",
            "device",
            "-----BEGIN CERTIFICATE-----\nexample\n-----END CERTIFICATE-----",
        )
        original_socket = firebase.socket

        class FailingSocket:
            SOCK_STREAM = 1

            @staticmethod
            def getaddrinfo(*args):
                raise OSError("DNS unavailable")

        firebase.socket = FailingSocket
        try:
            with self.assertRaises(FirebaseError):
                reporter.report({"event": "status"})
        finally:
            firebase.socket = original_socket


if __name__ == "__main__":
    unittest.main()
