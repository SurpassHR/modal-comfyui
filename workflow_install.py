from __future__ import annotations

import shlex
from urllib.parse import urlsplit


DEFAULT_WORKFLOWS_DIR = "/root/comfy/ComfyUI/user/default/workflows"


def workflow_clone_command(
    repo_url: str,
    *,
    ref: str = "master",
    workflows_dir: str = DEFAULT_WORKFLOWS_DIR,
) -> str:
    """Build a shell command that installs repository contents as workflows.

    The GitHub token is read from ``GITHUB_TOKEN`` by a temporary Git credential
    helper. It is never placed in the repository URL or persisted in .git/config.
    Repository contents are merged directly into ``workflows_dir`` so ComfyUI
    does not display an extra repository-name folder.
    """
    parsed_url = urlsplit(repo_url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "github.com"
        or parsed_url.username
        or parsed_url.password
    ):
        raise ValueError("Workflow repositories must use plain GitHub HTTPS URLs")
    if not ref or ref.startswith("-") or any(ch.isspace() for ch in ref):
        raise ValueError("Workflow repository ref must be a valid branch or tag name")

    credential_helper = (
        'credential.helper=!f() { echo "username=x-access-token"; '
        'echo "password=$GITHUB_TOKEN"; }; f'
    )
    # Modal's image builder treats each newline in a RUN command as a new
    # Dockerfile instruction, so keep this command on one physical line.
    return "; ".join(
        [
            "set -eu",
            'test -n "${GITHUB_TOKEN:-}" || '
            '{ echo "GITHUB_TOKEN is required to clone private workflow repositories" >&2; exit 1; }',
            f"mkdir -p {shlex.quote(workflows_dir)}",
            'tmp_dir="$(mktemp -d)"',
            'cleanup() { rm -rf "$tmp_dir"; }',
            "trap cleanup EXIT",
            "GIT_TERMINAL_PROMPT=0 git -c credential.helper= "
            f"-c {shlex.quote(credential_helper)} "
            "clone --depth 1 --single-branch "
            f"--branch {shlex.quote(ref)} {shlex.quote(repo_url)} \"$tmp_dir/repo\"",
            'rm -rf "$tmp_dir/repo/.git"',
            'test -n "$(find "$tmp_dir/repo" -type f -name \'*.json\' -print -quit)"',
            f"cp -a \"$tmp_dir/repo/.\" {shlex.quote(workflows_dir)}/",
        ]
    )
