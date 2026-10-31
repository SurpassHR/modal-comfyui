from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from user_volume import seed_user_directory


class UserVolumeSeedTest(unittest.TestCase):
    def test_copies_missing_defaults_without_overwriting_user_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            defaults = root / "defaults"
            user = root / "user"
            (defaults / "default" / "workflows").mkdir(parents=True)
            (defaults / "default" / "workflows" / "new.json").write_text('{"new": true}')
            (defaults / "README.txt").write_text("default")
            user.mkdir()
            (user / "README.txt").write_text("user-modified")

            changed = seed_user_directory(defaults, user)

            self.assertTrue(changed)
            self.assertEqual((user / "README.txt").read_text(), "user-modified")
            self.assertEqual(
                (user / "default" / "workflows" / "new.json").read_text(),
                '{"new": true}',
            )

    def test_is_idempotent_and_handles_missing_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            defaults = root / "missing"
            user = root / "user"
            self.assertFalse(seed_user_directory(defaults, user))
            self.assertFalse(seed_user_directory(defaults, user))


if __name__ == "__main__":
    unittest.main()
