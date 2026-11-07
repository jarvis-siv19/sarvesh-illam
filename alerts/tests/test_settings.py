import tempfile
import unittest
from pathlib import Path

from service.settings import load_config, merge_config


class SettingsTests(unittest.TestCase):
    def test_nested_local_config_overrides_only_its_house_values(self):
        merged = merge_config(
            {"camera_reconnect": {"fast_retries": 3, "offline_retry": 300}},
            {"camera_reconnect": {"fast_retries": 1}},
        )
        self.assertEqual(merged["camera_reconnect"], {
            "fast_retries": 1,
            "offline_retry": 300,
        })

    def test_load_config_works_without_local_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "config.yaml").write_text("api_port: 8090\n")
            self.assertEqual(load_config(path), {"api_port": 8090})


if __name__ == "__main__":
    unittest.main()
