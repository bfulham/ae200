"""Protocol tests that do not require Home Assistant."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "custom_components" / "ae200"

# Load the package modules without importing Home Assistant.
package = types.ModuleType("custom_components")
package.__path__ = [str(ROOT / "custom_components")]
sys.modules["custom_components"] = package

ae200_package = types.ModuleType("custom_components.ae200")
ae200_package.__path__ = [str(PACKAGE)]
sys.modules["custom_components.ae200"] = ae200_package


def load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"custom_components.ae200.{name}",
        PACKAGE / f"{name}.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


const = load("const")
protocol = load("protocol")


class RequestTests(unittest.TestCase):
    def test_status_request_batches_only_requested_groups(self):
        payload = protocol.build_status_request(["1", "42"])
        root = ET.fromstring(payload)
        nodes = root.findall("./DatabaseManager/Mnet")
        self.assertEqual(
            [node.get("Group") for node in nodes],
            ["1", "42"],
        )
        self.assertEqual(root.findtext("./Command"), "getRequest")
        self.assertIsNone(nodes[0].get("DriveStatus"))
        self.assertIsNone(nodes[0].get("ErrorCode"))
        self.assertEqual(nodes[0].get("Mode"), "*")

    def test_write_targets_exactly_one_group(self):
        payload, normalised = protocol.build_set_request(
            "7",
            {"Mode": "AUTO"},
        )
        root = ET.fromstring(payload)
        nodes = root.findall("./DatabaseManager/Mnet")
        self.assertEqual(len(nodes), 1)
        self.assertEqual(
            nodes[0].attrib,
            {"Group": "7", "Mode": "AUTO"},
        )
        self.assertEqual(normalised, {"Mode": "AUTO"})

    def test_auto_readback_states_match_auto_command(self):
        self.assertTrue(
            protocol.values_match("Mode", "AUTO", "AUTOCOOL")
        )
        self.assertTrue(
            protocol.values_match("Mode", "AUTO", "AUTOHEAT")
        )
        self.assertFalse(
            protocol.values_match("Mode", "AUTO", "COOL")
        )

    def test_set_request_rejects_unsupported_attribute(self):
        with self.assertRaises(protocol.AE200WriteError):
            protocol.build_set_request(
                "1",
                {"Schedule": "ON"},
            )

    def test_set_request_rejects_multiple_target_injection(self):
        payload, _ = protocol.build_set_request(
            '1"><Mnet Group="2',
            {"Drive": "ON"},
        )
        root = ET.fromstring(payload)
        nodes = root.findall("./DatabaseManager/Mnet")
        self.assertEqual(len(nodes), 1)
        self.assertEqual(
            nodes[0].get("Group"),
            '1"><Mnet Group="2',
        )


class ParsingTests(unittest.TestCase):
    def test_parse_discovery(self):
        xml = """<Packet><DatabaseManager><ControlGroup><MnetList>
        <MnetRecord Group="2" GroupNameWeb="Office" />
        <MnetRecord Group="1" GroupNameWeb="Reception" />
        </MnetList></ControlGroup></DatabaseManager></Packet>"""
        groups = protocol.parse_discovery(xml)
        self.assertEqual(groups["1"].name, "Reception")
        self.assertEqual(groups["2"].name, "Office")

    def test_parse_get_error_response_preserves_status(self):
        xml = """<Packet><Command>getErrorResponse</Command>
        <DatabaseManager>
          <Mnet Group="1" Drive="ON" Mode="AUTOCOOL" />
          <ERROR Point="ErrorCode" Code="0101"
                 Message="Unknown Attribute" />
        </DatabaseManager></Packet>"""
        result = protocol.parse_status(xml)
        self.assertEqual(result.statuses["1"]["Mode"], "AUTOCOOL")
        self.assertEqual(result.errors[0]["Code"], "0101")


if __name__ == "__main__":
    unittest.main()
