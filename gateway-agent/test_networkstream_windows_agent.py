import importlib.util
import json
from pathlib import Path
from unittest import TestCase, mock

MODULE_PATH = Path(__file__).with_name("networkstream-windows-agent.py")
spec = importlib.util.spec_from_file_location("networkstream_windows_agent", MODULE_PATH)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


class WindowsGatewayTests(TestCase):
    def test_scan_parses_real_netsh_shape(self):
        output = """
SSID 1 : NS-UPLINK-A
    Network type : Infrastructure
    Authentication : WPA2-Personal
    Encryption : CCMP
    BSSID 1 : AA:BB:CC:DD:EE:01
         Signal : 82%
         Channel : 6

SSID 2 : NS-TEST-B
    Network type : Infrastructure
    Authentication : Open
    Encryption : None
    BSSID 1 : AA:BB:CC:DD:EE:02
         Signal : 61%
         Channel : 36
"""
        completed = mock.Mock(returncode=0, stdout=output, stderr="")
        with mock.patch.object(agent, "run", return_value=completed):
            networks = agent.scan()
        self.assertEqual(2, len(networks))
        self.assertEqual("NS-UPLINK-A", networks[0]["ssid"])
        self.assertEqual("aa:bb:cc:dd:ee:01", networks[0]["bssid"])
        self.assertEqual(82, networks[0]["signalPercent"])
        self.assertIsNone(networks[0]["signalDbm"])
        self.assertEqual("2437 MHz", networks[0]["frequency"])
        self.assertIn("WPA2-Personal", networks[0]["security"])
        self.assertEqual("5180 MHz", networks[1]["frequency"])

    def test_scan_does_not_report_percentage_as_dbm(self):
        output = """SSID 1 : Test
    BSSID 1 : AA:BB:CC:DD:EE:FF
         Signal : 90%
         Channel : 11
"""
        completed = mock.Mock(returncode=0, stdout=output, stderr="")
        with mock.patch.object(agent, "run", return_value=completed):
            network = agent.scan()[0]
        self.assertEqual(90, network["signalPercent"])
        self.assertIsNone(network["signalDbm"])

    def test_clients_filters_to_mobile_hotspot_hosts(self):
        output = """Interface: 192.168.137.1 --- 0xb
  Internet Address      Physical Address      Type
  192.168.137.1         00-11-22-33-44-55     dynamic
  192.168.137.23        aa-bb-cc-dd-ee-ff     dynamic
  192.168.137.255       ff-ff-ff-ff-ff-ff     static
  192.168.42.109        11-22-33-44-55-66     dynamic
"""
        completed = mock.Mock(returncode=0, stdout=output, stderr="")
        with mock.patch.object(agent, "run", return_value=completed):
            found = agent.clients()
        self.assertEqual(
            [{"ipAddress": "192.168.137.23", "macAddress": "aa:bb:cc:dd:ee:ff", "hostname": None}],
            found,
        )

    def test_valid_client_rejects_non_downstream_address(self):
        with self.assertRaises(ValueError):
            agent.valid_client("192.168.42.10")

    def test_valid_client_rejects_broadcast_address(self):
        with self.assertRaises(ValueError):
            agent.valid_client("192.168.137.255")

    def test_new_client_is_denied_by_default(self):
        state = agent.TrafficState()
        self.assertFalse(state.is_authorized("192.168.137.23"))

    def test_allow_and_block_change_policy_without_firewall_rules(self):
        state = agent.TrafficState()
        ip = "192.168.137.23"
        state.set_authorized(ip, True)
        self.assertTrue(state.is_authorized(ip))
        state.set_authorized(ip, False)
        self.assertFalse(state.is_authorized(ip))

    def test_traffic_counters_distinguish_forwarded_and_dropped_packets(self):
        state = agent.TrafficState()
        ip = "192.168.137.23"
        state.record(ip, False, 100)
        state.record(ip, True, 250)
        snapshot = state.snapshot_traffic(ip)
        self.assertEqual(1, snapshot["droppedPackets"])
        self.assertEqual(100, snapshot["droppedBytes"])
        self.assertEqual(1, snapshot["forwardedPackets"])
        self.assertEqual(250, snapshot["forwardedBytes"])
        self.assertIsNotNone(snapshot["lastTrafficAt"])

    def test_post_accepts_json_response(self):
        response = mock.MagicMock()
        response.read.return_value = json.dumps({"status": "OK"}).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with mock.patch.object(agent.urllib.request, "urlopen", return_value=response):
            result = agent.post("http://localhost:8080/api/gateways/GW-1/scan", {"gatewayId": "GW-1"})
        self.assertEqual({"status": "OK"}, result)

    def test_online_returns_false_on_timeout(self):
        with mock.patch.object(agent.urllib.request, "urlopen", side_effect=TimeoutError()):
            self.assertFalse(agent.online())


if __name__ == "__main__":
    import unittest
    unittest.main()
