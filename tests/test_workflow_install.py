from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from workflow_install import workflow_clone_command


class WorkflowCloneCommandTest(unittest.TestCase):
    def test_copies_repository_contents_directly_into_workflow_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_git = bin_dir / "git"
            fake_git.write_text(
                "#!/bin/sh\n"
                "for last do :; done\n"
                'mkdir -p "$last/subdir" "$last/.git"\n'
                'printf "{}\\n" > "$last/workflow.json"\n'
                'printf "{}\\n" > "$last/subdir/other.json"\n',
                encoding="utf-8",
            )
            fake_git.chmod(0o755)

            workflows_dir = root / "workflows"
            workflows_dir.mkdir()
            (workflows_dir / "keep.json").write_text("{}", encoding="utf-8")
            command = workflow_clone_command(
                "https://github.com/owner/private-workflows.git",
                ref="main",
                workflows_dir=str(workflows_dir),
            )
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            env["GITHUB_TOKEN"] = "test-token"
            result = subprocess.run(
                ["bash", "-c", command],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((workflows_dir / "workflow.json").is_file())
            self.assertTrue((workflows_dir / "subdir" / "other.json").is_file())
            self.assertTrue((workflows_dir / "keep.json").is_file())
            self.assertFalse((workflows_dir / "private-workflows").exists())
            self.assertFalse((workflows_dir / ".git").exists())
            self.assertNotIn("test-token", command)

    def test_requires_github_token(self) -> None:
        command = workflow_clone_command(
            "https://github.com/owner/private-workflows.git",
        )
        env = os.environ.copy()
        env.pop("GITHUB_TOKEN", None)
        result = subprocess.run(
            ["bash", "-c", command],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GITHUB_TOKEN is required", result.stderr)

    def test_rejects_non_github_https_repository(self) -> None:
        with self.assertRaises(ValueError):
            workflow_clone_command(
                "https://example.com/private-workflows.git",
            )


if __name__ == "__main__":
    unittest.main()
