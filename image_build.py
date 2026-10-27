from __future__ import annotations

import shlex


DEFAULT_COMFY_CUDA_VERSION = "13.0"


def comfy_install_command(
    comfy_version: str | None = None,
    cuda_version: str | None = DEFAULT_COMFY_CUDA_VERSION,
) -> str:
    """Build the ComfyUI install command used by the Modal image."""
    cuda_opt = (
        f"--cuda-version {shlex.quote(cuda_version)} " if cuda_version else ""
    )
    version_opt = (
        f"--version {shlex.quote(comfy_version)} " if comfy_version else ""
    )
    return f"comfy --skip-prompt install --nvidia {cuda_opt}{version_opt}".rstrip()
