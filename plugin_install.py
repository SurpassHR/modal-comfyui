from __future__ import annotations

import shlex
from collections.abc import Sequence
from urllib.parse import urlsplit


DEFAULT_REQUIREMENTS_FILES = ("requirements.txt",)
DEFAULT_CONSTRAINTS_FILE = "/tmp/modal-comfyui-constraints.txt"
_CORE_PACKAGES_PATTERN = (
    "^(torch|torchvision|torchaudio|torchcodec|numpy|opencv[-_].*|"
    "triton|nvidia-.*|xformers)=="
)


def core_constraints_command(
    constraints_file: str = DEFAULT_CONSTRAINTS_FILE,
) -> str:
    """Pin the installed CUDA and numeric stack before adding node dependencies."""
    return (
        "set -eu; python -m pip freeze | "
        f"grep -Ei {shlex.quote(_CORE_PACKAGES_PATTERN)} "
        f"> {shlex.quote(constraints_file)}; "
        f"test -s {shlex.quote(constraints_file)}"
    )


def git_clone_command(
    repo_url: str,
    destination: str,
    *,
    branch: str = "",
    recurse_submodules: bool = True,
    retries: int = 3,
    timeout_seconds: int = 180,
    retry_delay_seconds: int = 5,
) -> str:
    """Build a retrying, shallow Git clone command for a Modal Image layer."""
    parsed_url = urlsplit(repo_url)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
    ):
        raise ValueError("Git repositories must use a plain HTTPS URL")
    if branch and (branch.startswith("-") or any(ch.isspace() for ch in branch)):
        raise ValueError("Git branch must be a valid branch or tag name")
    if retries < 1:
        raise ValueError("retries must be at least 1")
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be at least 1")

    branch_opt = f"--branch {shlex.quote(branch)} " if branch else ""
    submodule_opt = "--recurse-submodules --shallow-submodules " if recurse_submodules else ""
    # Modal's image builder treats newlines inside RUN as new instructions.
    return " ".join(
        [
            "set -eu;",
            "attempt=0;",
            "clone_ok=0;",
            f'while [ "$attempt" -lt {retries} ]; do',
            "attempt=$((attempt + 1));",
            f"rm -rf {shlex.quote(destination)};",
            "if GIT_TERMINAL_PROMPT=0 "
            f"timeout {timeout_seconds} "
            "git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=30 "
            "clone --depth 1 --single-branch "
            f"{submodule_opt}{branch_opt}{shlex.quote(repo_url)} "
            f"{shlex.quote(destination)}; then clone_ok=1; break; fi;",
            f'if [ "$attempt" -lt {retries} ]; then sleep {retry_delay_seconds}; fi;',
            "done;",
            f'[ "$clone_ok" = 1 ] || {{ echo "git clone failed after {retries} attempts: {repo_url}" >&2; exit 1; }}',
        ]
    )


def requirements_install_command(
    work_dir: str,
    requirements: Sequence[str] | None,
    constraints_file: str | None = DEFAULT_CONSTRAINTS_FILE,
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
    constraint_opt = (
        f"--constraint {shlex.quote(constraints_file)} " if constraints_file else ""
    )
    return (
        f"cd {shlex.quote(work_dir)} && "
        f"for req_file in {quoted_files}; do "
        f'if [ -f "$req_file" ]; then '
        f'uv pip install {constraint_opt}--python "$(command -v python)" '
        f'--compile-bytecode -r "$req_file"; '
        f'else echo "Skipping missing requirements file: $PWD/$req_file"; fi; '
        f"done"
    )
