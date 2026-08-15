import importlib.util
from pathlib import Path
from unittest import TestCase, mock


MODULE_PATH = Path(__file__).with_name("networkstream-windows-agent.py")
spec = importlib.util.spec_from_file_location("networkstream_windows_agent", MODULE_PATH)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


class WindowsWifiScanTests(TestCase):
    def test_scan_wifi_parses_real_netsh_shape(self):
        output = """
SSID 1 : NS-UPLINK-A
    Network type            : Infrastructure
    Authentication          : WPA2-Personal
    Encryption              : CCMP
    BSSID 1                 : AA:BB:CC:DD:EE:01
         Signal             : 82%
         Channel            : 6

SSID 2 : NS-TEST-B
    Network type            : Infrastructure
    Authentication          : Open
    Encryption              : None
    BSSID 1                 : AA:BB:CC:DD:EE:02
         Signal             : 61%
         Channel            : 36
"""
        completed = mock.Mock(returncode=0, stdout=output, stderr="")
        with mock.patch.object(agent, "run", return_value=completed):
            networks = agent.scan_wifi()

        self.assertEqual(2, len(networks))
        self.assertEqual("NS-UPLINK-A", networks[0]["ssid"])
        self.assertEqual("aa:bb:cc:dd:ee:01", networks[0]["bssid"])
        self.assertEqual(82, networks[0]["signalPercent"])
        self.assertIsNone(networks[0]["signalDbm"])
        self.assertEqual("2437 MHz", networks[0]["frequency"])
        self.assertIn("WPA2-Personal", networks[0]["security"])
        self.assertEqual("5180 MHz", networks[1]["frequency"])
        self.assertEqual("Open", networks[1]["security"])

    def test_scan_wifi_does_not_report_signal_percentage_as_dbm(self):
        output = """
SSID 1 : Test
    BSSID 1 : AA:BB:CC:DD:EE:FF
         Signal : 90%
         Channel : 11
"""
        completed = mock.Mock(returncode=0, stdout=output, stderr="")
        with mock.patch.object(agent, "run", return_value=completed):
            network = agent.scan_wifi()[0]

        self.assertEqual(90, network["signalPercent"])
        self.assertIsNone(network["signalDbm"])

    def test_scan_wifi_raises_when_netsh_fails(self):
        completed = mock.Mock(returncode=1, stdout="", stderr="WLAN AutoConfig service is not running")
        with mock.patch.object(agent, "run", return_value=completed):
            with self.assertRaises(RuntimeError):
                agent.scan_wifi()


if __name__ == "__main__":
    import unittest
    unittest.main()
