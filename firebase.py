"""Minimal HTTPS Firebase Realtime Database REST event reporter."""

try:
    import ujson as json
except ImportError:
    import json

try:
    import socket
    import ssl
except ImportError:
    socket = None
    ssl = None

try:
    import utime as _time

    def _ticks_ms():
        return _time.ticks_ms()
except ImportError:
    import time as _time

    def _ticks_ms():
        return int(_time.time() * 1000)


class FirebaseError(Exception):
    pass


class FirebaseReporter:
    def __init__(self, database_url, auth_token, device_id, ca_certificate,
                 timeout_s=8):
        self.database_url = (database_url or "").rstrip("/")
        self.auth_token = auth_token
        self.device_id = device_id
        self.ca_certificate = ca_certificate
        self.timeout_s = timeout_s
        self._event_counter = 0

    @property
    def configured(self):
        return bool(
            self.database_url and self.auth_token and self.device_id and
            self.ca_certificate
        )

    @property
    def partially_configured(self):
        return bool(self.database_url or self.auth_token or self.ca_certificate)

    def report(self, event):
        if not self.configured:
            raise FirebaseError("Firebase is not configured in secrets.py")
        host, base_path = self._parse_url()
        self._event_counter = (self._event_counter + 1) % 10000
        event_id = "%d-%04d" % (_ticks_ms(), self._event_counter)
        path = "%s/fingerprint_events/%s/%s.json?auth=%s" % (
            base_path,
            self._url_component(self.device_id),
            event_id,
            self._url_component(self.auth_token),
        )
        payload = json.dumps(event).encode("utf-8")
        response = self._request(host, path, payload)
        status_line = response.split(b"\r\n", 1)[0]
        if not (status_line.startswith(b"HTTP/1.1 2") or
                status_line.startswith(b"HTTP/1.0 2")):
            raise FirebaseError(
                "Firebase returned %s" % status_line.decode("utf-8", "replace")
            )
        return event_id

    def _parse_url(self):
        prefix = "https://"
        if not self.database_url.startswith(prefix):
            raise FirebaseError("Firebase database URL must start with https://")
        remainder = self.database_url[len(prefix):]
        host, separator, path = remainder.partition("/")
        if not host:
            raise FirebaseError("Firebase database URL has no host")
        return host, ("/" + path.strip("/")) if separator and path else ""

    def _request(self, host, path, payload):
        if socket is None or ssl is None:
            raise FirebaseError("MicroPython socket/ssl modules are unavailable")
        raw_socket = None
        secure_socket = None
        try:
            address = socket.getaddrinfo(host, 443, 0, socket.SOCK_STREAM)[0][-1]
            raw_socket = socket.socket()
            raw_socket.settimeout(self.timeout_s)
            raw_socket.connect(address)
            try:
                secure_socket = ssl.wrap_socket(
                    raw_socket,
                    server_hostname=host,
                    cert_reqs=ssl.CERT_REQUIRED,
                    cadata=self.ca_certificate,
                )
            except (AttributeError, TypeError):
                raise FirebaseError(
                    "Firmware ssl.wrap_socket lacks certificate validation support"
                )
            request = (
                "PUT %s HTTP/1.1\r\n"
                "Host: %s\r\n"
                "Content-Type: application/json\r\n"
                "Content-Length: %d\r\n"
                "Connection: close\r\n\r\n"
            ) % (path, host, len(payload))
            secure_socket.write(request.encode("ascii"))
            secure_socket.write(payload)
            response = bytearray()
            while True:
                chunk = secure_socket.read(128)
                if not chunk:
                    break
                response.extend(chunk)
                if len(response) > 4096:
                    break
            return bytes(response)
        except OSError as error:
            raise FirebaseError("Firebase network request failed: %s" % error)
        finally:
            if secure_socket:
                secure_socket.close()
            elif raw_socket:
                raw_socket.close()

    @staticmethod
    def _url_component(value):
        safe = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
        output = []
        for byte in str(value).encode("utf-8"):
            if byte in safe:
                output.append(chr(byte))
            else:
                output.append("%%%02X" % byte)
        return "".join(output)
