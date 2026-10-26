from __future__ import annotations

import shlex
from collections.abc import Sequence


DEFAULT_REQUIREMENTS_FILES = ("requirements.txt",)


def requirements_install_command(
    work_dir: str,
    requirements: Sequence[str] | None,
) -> str | None:
    """Build a shell command that installs every requirement file that exists.

    ``None`` auto-detects the conventional ``requirements.txt`` file. An empty
    sequence disables dependency installation for the plugin.
    """
    if requirements is None:
        requirements = DEFAULT_REQUIREMENTS_FILES
    if not requirements:
        return None

    quoted_files = " ".join(shlex.quote(path) for path in requirements)
    return (
        f"cd {shlex.quote(work_dir)} && "
        f"for req_file in {quoted_files}; do "
        f'if [ -f "$req_file" ]; then '
        f'uv pip install --no-deps --python "$(command -v python)" '
        f'--compile-bytecode -r "$req_file"; '
        f'else echo "Skipping missing requirements file: $PWD/$req_file"; fi; '
        f"done"
    )
