from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class ImagePackagingTest(unittest.TestCase):
    def test_all_local_top_level_imports_are_added_to_image(self) -> None:
        source = (ROOT_DIR / "comfyui.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        local_modules = {
            path.stem
            for path in ROOT_DIR.glob("*.py")
            if path.stem != "comfyui"
        }

        imported_modules = {
            node.module
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module in local_modules
        }
        copied_modules: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "add_local_python_source":
                continue
            copied_modules.update(
                arg.value
                for arg in node.args
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            )

        self.assertLessEqual(imported_modules, copied_modules)


if __name__ == "__main__":
    unittest.main()
