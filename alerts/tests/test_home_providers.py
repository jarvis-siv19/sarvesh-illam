import tempfile
import unittest
from pathlib import Path

from service.home import HomeAssistant


class FakeProvider:
    name = "local_test"
    enabled = True

    def __init__(self):
        self.last_command = None

    def entities(self):
        return [{
            "id": "test_switch",
            "entity_id": "local_test.device.switch",
            "name": "Test switch",
            "room": "Lab",
            "icon": "T",
            "type": "switch",
            "read_only": False,
            "provider": self.name,
        }]

    def states(self):
        return [{"id": "test_switch", "state": "on", "attributes": {"source": "test"}}]

    def command(self, item_id, action, data=None):
        self.last_command = (item_id, action, data)
        return {"ok": True}


class HomeProviderTests(unittest.TestCase):
    def test_local_provider_works_without_home_assistant_credentials(self):
        provider = FakeProvider()
        with tempfile.TemporaryDirectory() as directory:
            home = HomeAssistant({}, Path(directory) / "layout.json", providers=[provider])
            self.assertTrue(home.enabled)
            self.assertTrue(home.public_config()["configured"])
            self.assertEqual(home.states()[0]["state"], "on")
            home.command("test_switch", "turn_off")
        self.assertEqual(provider.last_command, ("test_switch", "turn_off", None))


if __name__ == "__main__":
    unittest.main()
