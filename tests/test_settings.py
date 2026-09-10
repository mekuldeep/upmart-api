import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite://")

from routers import settings


class SettingsTests(unittest.TestCase):
    def test_old_settings_file_receives_default_whatsapp_number(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_file = Path(temp_dir) / "settings.json"
            settings_file.write_text(json.dumps({"siteEmail": "store@example.com"}))

            with patch.object(settings, "SETTINGS_FILE", str(settings_file)):
                loaded = settings.load_settings()

            self.assertEqual(loaded["whatsappNumber"], "919876543210")

    def test_settings_routes_persist_and_return_admin_whatsapp_number(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_file = Path(temp_dir) / "settings.json"

            with patch.object(settings, "SETTINGS_FILE", str(settings_file)):
                update_response = settings.update_settings(
                    {"whatsappNumber": "+91 97993 77544"},
                    current_admin=object(),
                )
                get_response = settings.get_settings()
                persisted = json.loads(settings_file.read_text())

            self.assertEqual(update_response["whatsappNumber"], "+91 97993 77544")
            self.assertEqual(get_response["whatsappNumber"], "+91 97993 77544")
            self.assertEqual(persisted["whatsappNumber"], "+91 97993 77544")


if __name__ == "__main__":
    unittest.main()
