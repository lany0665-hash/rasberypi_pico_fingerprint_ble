"""Pico W Wi-Fi helper with explicit configuration and timeout failures."""

try:
    import network
except ImportError:
    network = None

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


class WiFiError(Exception):
    pass


class WiFiManager:
    def __init__(self, ssid, password, timeout_ms=15000):
        self.ssid = ssid
        self.password = password
        self.timeout_ms = timeout_ms
        self.wlan = None

    @property
    def configured(self):
        return bool(self.ssid and self.password)

    def connect(self):
        if not self.configured:
            raise WiFiError("Wi-Fi is not configured in secrets.py")
        if network is None:
            raise WiFiError("MicroPython network module is unavailable")
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        if self.wlan.isconnected():
            return self.wlan.ifconfig()
        self.wlan.connect(self.ssid, self.password)
        started = _ticks_ms()
        while not self.wlan.isconnected():
            if _ticks_diff(_ticks_ms(), started) >= self.timeout_ms:
                status = self.wlan.status()
                raise WiFiError("Wi-Fi connection timed out (status %s)" % status)
            _sleep_ms(200)
        return self.wlan.ifconfig()

    @staticmethod
    def sync_time():
        """Set the UTC clock required for certificate validation."""
        try:
            import ntptime
        except ImportError:
            raise WiFiError("MicroPython ntptime module is unavailable for TLS validation")
        try:
            ntptime.settime()
        except OSError as error:
            raise WiFiError("NTP time synchronization failed: %s" % error)
