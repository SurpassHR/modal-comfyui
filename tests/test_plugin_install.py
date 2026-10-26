from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from plugin_install import requirements_install_command


class RequirementsInstallCommandTest(unittest.TestCase):
    def _run_command(
        self,
        work_dir: Path,
        requirements: list[str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], list[str]]:
        command = requirements_install_command(str(work_dir), requirements)
        self.assertIsNotNone(command)

        with tempfile.TemporaryDirectory() as bin_dir:
            log_path = Path(bin_dir) / "uv.log"
            uv_path = Path(bin_dir) / "uv"
            uv_path.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$@" > "$UV_LOG"\n',
                encoding="utf-8",
            )
            uv_path.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            env["UV_LOG"] = str(log_path)
            result = subprocess.run(
                ["bash", "-c", command],
                cwd=work_dir,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            args = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []

        return result, args

    def test_installs_requirements_txt_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as work_dir:
            path = Path(work_dir)
            (path / "requirements.txt").write_text("opencv-python-headless\n", encoding="utf-8")

            result, args = self._run_command(path)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-r", args)
        self.assertIn("requirements.txt", args)

    def test_skips_missing_requirements_txt_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as work_dir:
            result, args = self._run_command(Path(work_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(args, [])
        self.assertIn("Skipping missing requirements file", result.stdout)

    def test_empty_requirements_disables_dependency_install(self) -> None:
        self.assertIsNone(requirements_install_command("/tmp/plugin", []))


if __name__ == "__main__":
    unittest.main()
