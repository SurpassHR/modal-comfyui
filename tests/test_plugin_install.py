from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from plugin_install import (
    DEFAULT_CONSTRAINTS_FILE,
    core_constraints_command,
    git_clone_command,
    requirements_install_command,
)


class GitCloneCommandTest(unittest.TestCase):
    def test_retries_transient_clone_failure_and_uses_shallow_clone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()

            git_path = bin_dir / "git"
            git_path.write_text(
                "#!/bin/sh\n"
                "for last do :; done\n"
                'count=0\n'
                'if [ -f "$GIT_COUNT" ]; then count=$(cat "$GIT_COUNT"); fi\n'
                'count=$((count + 1))\n'
                'printf "%s" "$count" > "$GIT_COUNT"\n'
                'if [ "$count" -lt 2 ]; then exit 128; fi\n'
                'mkdir -p "$last"\n'
                'printf "ok\\n" > "$last/__init__.py"\n',
                encoding="utf-8",
            )
            git_path.chmod(0o755)

            timeout_path = bin_dir / "timeout"
            timeout_path.write_text('#!/bin/sh\nshift\nexec "$@"\n', encoding="utf-8")
            timeout_path.chmod(0o755)

            destination = root / "custom_nodes" / "plugin"
            command = git_clone_command(
                "https://github.com/owner/plugin.git",
                str(destination),
                retries=3,
                timeout_seconds=30,
                retry_delay_seconds=0,
            )
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            env["GIT_COUNT"] = str(root / "git-count")
            result = subprocess.run(
                ["bash", "-c", command],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "git-count").read_text(), "2")
            self.assertTrue((destination / "__init__.py").is_file())
            self.assertNotIn("\n", command)
            self.assertIn("--depth 1", command)

    def test_reports_failure_after_all_retries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (bin_dir / "git").write_text("#!/bin/sh\nexit 128\n", encoding="utf-8")
            (bin_dir / "git").chmod(0o755)
            (bin_dir / "timeout").write_text(
                '#!/bin/sh\nshift\nexec "$@"\n', encoding="utf-8"
            )
            (bin_dir / "timeout").chmod(0o755)

            command = git_clone_command(
                "https://github.com/owner/plugin.git",
                str(root / "plugin"),
                retries=2,
                timeout_seconds=30,
                retry_delay_seconds=0,
            )
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
                ["bash", "-c", command],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("after 2 attempts", result.stderr)


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
        self.assertIn("--constraint", args)
        self.assertIn(DEFAULT_CONSTRAINTS_FILE, args)
        self.assertNotIn("--no-deps", args)

    def test_skips_missing_requirements_txt_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as work_dir:
            result, args = self._run_command(Path(work_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(args, [])
        self.assertIn("Skipping missing requirements file", result.stdout)

    def test_empty_requirements_disables_dependency_install(self) -> None:
        self.assertIsNone(requirements_install_command("/tmp/plugin", []))

    def test_core_constraints_command_pins_torch_ecosystem(self) -> None:
        command = core_constraints_command()
        self.assertNotIn("\n", command)
        self.assertIn("pip freeze", command)
        self.assertIn("torch", command)
        self.assertIn(DEFAULT_CONSTRAINTS_FILE, command)


if __name__ == "__main__":
    unittest.main()
