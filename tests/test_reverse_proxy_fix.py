from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class FakeResource:
    def __init__(self, canonical: str) -> None:
        self.canonical = canonical


class FakeRoute:
    def __init__(self, method: str, canonical: str, handler: object) -> None:
        self.method = method
        self.resource = FakeResource(canonical)
        self.handler = handler


class FakeRouter:
    def __init__(self, routes: list[FakeRoute]) -> None:
        self._routes = routes
        self.added: list[tuple[str, str, object]] = []

    def routes(self):
        return self._routes

    def add_route(self, method: str, path: str, handler: object) -> None:
        self.added.append((method, path, handler))


class FakePromptServer:
    def add_routes(self) -> None:
        pass


class ReverseProxyFixTest(unittest.TestCase):
    def _load_module(self):
        fake_server = types.ModuleType("server")
        fake_server.PromptServer = FakePromptServer
        previous = sys.modules.get("server")
        sys.modules["server"] = fake_server
        try:
            spec = importlib.util.spec_from_file_location(
                "reverse_proxy_fix_under_test",
                ROOT_DIR / "vendor_nodes" / "reverse_proxy_fix" / "__init__.py",
            )
            self.assertIsNotNone(spec)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        finally:
            if previous is None:
                sys.modules.pop("server", None)
            else:
                sys.modules["server"] = previous

    def test_registers_get_route_for_decoded_workflow_paths(self) -> None:
        module = self._load_module()
        get_handler = object()
        post_handler = object()
        delete_handler = object()
        app = types.SimpleNamespace(
            router=FakeRouter(
                [
                    FakeRoute("GET", "/userdata/{file}", get_handler),
                    FakeRoute("POST", "/userdata/{file}", post_handler),
                    FakeRoute("DELETE", "/userdata/{file}", delete_handler),
                    FakeRoute("GET", "/userdata", object()),
                    FakeRoute("POST", "/userdata/{file}/move/{dest}", object()),
                    FakeRoute("GET", "/api/userdata/{file}", get_handler),
                ]
            )
        )

        module._register_slash_tolerant_userdata(app)

        self.assertIn(("GET", "/userdata/{file:.+}", get_handler), app.router.added)
        self.assertIn(("POST", "/userdata/{file:.+}", post_handler), app.router.added)
        self.assertIn(("DELETE", "/userdata/{file:.+}", delete_handler), app.router.added)
        self.assertIn(("GET", "/api/userdata/{file:.+}", get_handler), app.router.added)
        self.assertNotIn(("GET", "/userdata{file:.+}", get_handler), app.router.added)


if __name__ == "__main__":
    unittest.main()
