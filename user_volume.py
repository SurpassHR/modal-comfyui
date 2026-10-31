from __future__ import annotations

import os
import shutil
from pathlib import Path


USER_VOLUME_NAME = "comfyui-user"
USER_DATA_DIR = "/root/comfy/ComfyUI/user"
USER_DEFAULTS_DIR = "/opt/modal-comfyui-user-defaults"


def seed_user_directory(defaults_dir: str | Path, user_dir: str | Path) -> bool:
    """Copy defaults that are missing, preserving user-created files."""
    source = Path(defaults_dir)
    target = Path(user_dir)
    if not source.is_dir():
        return False

    changed = False
    target.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(source, followlinks=False):
        root_path = Path(root)
        relative = root_path.relative_to(source)
        dest_dir = target / relative
        dest_dir.mkdir(parents=True, exist_ok=True)

        for dirname in dirs:
            src = root_path / dirname
            dst = dest_dir / dirname
            if src.is_symlink():
                if not dst.exists() and not dst.is_symlink():
                    dst.symlink_to(os.readlink(src), target_is_directory=True)
                    changed = True
            else:
                dst.mkdir(exist_ok=True)

        for filename in files:
            src = root_path / filename
            dst = dest_dir / filename
            if dst.exists() or dst.is_symlink():
                continue
            if src.is_symlink():
                dst.symlink_to(os.readlink(src))
            else:
                shutil.copy2(src, dst)
            changed = True

    return changed
