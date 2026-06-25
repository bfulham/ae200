"""Pure model tests without importing Home Assistant."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "custom_components" / "ae200"

custom_components = sys.modules.setdefault(
    "custom_components",
    types.ModuleType("custom_components"),
)
custom_components.__path__ = [str(ROOT / "custom_components")]

ae200_package = sys.modules.setdefault(
    "custom_components.ae200",
    types.ModuleType("custom_components.ae200"),
)
ae200_package.__path__ = [str(PACKAGE)]


def load(name: str):
    full_name = f"custom_components.ae200.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(
        full_name,
        PACKAGE / f"{name}.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


load("const")
protocol = load("protocol")
models = load("models")


class DataModelTests(unittest.TestCase):
    def test_stale_group_count(self):
        groups = {
            "1": protocol.AE200Group("1", "Office"),
            "2": protocol.AE200Group("2", "Reception"),
        }
        data = models.AE200Data(
            groups=groups,
            statuses={
                "1": {"Group": "1", "Drive": "ON"},
                "2": {"Group": "2", "Drive": "OFF"},
            },
            stale_groups=frozenset({"2"}),
            using_stale_data=True,
            consecutive_poll_failures=1,
            last_poll_error="timeout",
        )
        self.assertEqual(data.stale_group_count, 1)
        self.assertEqual(data.running_count, 1)
        self.assertTrue(data.using_stale_data)
        self.assertEqual(data.last_poll_error, "timeout")


if __name__ == "__main__":
    unittest.main()
