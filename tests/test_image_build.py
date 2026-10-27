from __future__ import annotations

import unittest

from image_build import comfy_install_command


class ComfyInstallCommandTest(unittest.TestCase):
    def test_uses_cuda_13_by_default(self) -> None:
        command = comfy_install_command()
        self.assertEqual(
            command,
            "comfy --skip-prompt install --nvidia --cuda-version 13.0",
        )

    def test_combines_cuda_and_comfyui_versions(self) -> None:
        command = comfy_install_command("0.42.0", "13.0")
        self.assertIn("--nvidia", command)
        self.assertIn("--cuda-version 13.0", command)
        self.assertIn("--version 0.42.0", command)

    def test_can_disable_explicit_cuda_version(self) -> None:
        command = comfy_install_command(None, None)
        self.assertNotIn("--cuda-version", command)


if __name__ == "__main__":
    unittest.main()
