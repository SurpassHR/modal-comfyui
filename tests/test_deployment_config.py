from __future__ import annotations

import ast
import unittest
from pathlib import Path

from deployment_config import (
    DEFAULT_GPU_FALLBACKS,
    parse_gpu_fallbacks,
    parse_regions,
)


ROOT_DIR = Path(__file__).resolve().parents[1]


class DeploymentConfigTest(unittest.TestCase):
    def test_gpu_default_fallback_order(self) -> None:
        self.assertEqual(parse_gpu_fallbacks(None), list(DEFAULT_GPU_FALLBACKS))
        self.assertEqual(parse_gpu_fallbacks(""), list(DEFAULT_GPU_FALLBACKS))
        self.assertEqual(parse_gpu_fallbacks(" , "), list(DEFAULT_GPU_FALLBACKS))

    def test_gpu_single_value_remains_a_string(self) -> None:
        self.assertEqual(parse_gpu_fallbacks("l4"), "L4")

    def test_gpu_list_is_normalized_and_deduplicated(self) -> None:
        self.assertEqual(
            parse_gpu_fallbacks(" l4, A10G, l4 , T4 "),
            ["L4", "A10G", "T4"],
        )

    def test_gpu_count_suffix_is_preserved(self) -> None:
        self.assertEqual(parse_gpu_fallbacks("l4:2, a10g:1"), ["L4:2", "A10G:1"])

    def test_regions_empty_means_global(self) -> None:
        self.assertIsNone(parse_regions(None))
        self.assertIsNone(parse_regions(""))
        self.assertIsNone(parse_regions(" , "))

    def test_regions_are_normalized_and_deduplicated(self) -> None:
        self.assertEqual(parse_regions(" US, eu , ap, us "), ["us", "eu", "ap"])
        self.assertEqual(parse_regions("AP-NORTHEAST"), "ap-northeast")


class ComfyUIDecoratorTest(unittest.TestCase):
    def test_cls_decorator_uses_deployment_config(self) -> None:
        tree = ast.parse((ROOT_DIR / "comfyui.py").read_text(encoding="utf-8"))
        cls_keywords = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr != "cls":
                continue
            cls_keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            break

        self.assertIsNotNone(cls_keywords)
        assert cls_keywords is not None
        for keyword, expected_name in (("gpu", "GPU_CONFIG"), ("region", "REGION_CONFIG")):
            value = cls_keywords.get(keyword)
            self.assertIsInstance(value, ast.Name)
            assert isinstance(value, ast.Name)
            self.assertEqual(value.id, expected_name)


if __name__ == "__main__":
    unittest.main()
