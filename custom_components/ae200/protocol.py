"""Low-level WebSocket/XML protocol for Mitsubishi AE-200 controllers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import re
from typing import Iterable, Mapping
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from aiohttp import (
    ClientConnectionError,
    ClientError,
    ClientSession,
    ClientWSTimeout,
    WSMsgType,
)

from .const import (
    ATTR_AIR_DIRECTION,
    ATTR_DRIVE,
    ATTR_FAN_SPEED,
    ATTR_MODE,
    ATTR_SET_TEMP,
    AUTO_RAW_MODES,
    KNOWN_AIR_DIRECTIONS,
    KNOWN_FAN_MODES,
    RAW_MODE_COOL,
    RAW_MODE_DRY,
    RAW_MODE_FAN,
    RAW_MODE_HEAT,
    STATUS_ATTRIBUTES,
    WRITABLE_ATTRIBUTES,
)

DISCOVERY_REQUEST = """<?xml version="1.0" encoding="UTF-8" ?>
<Packet>
  <Command>getRequest</Command>
  <DatabaseManager>
    <ControlGroup>
      <MnetList />
    </ControlGroup>
  </DatabaseManager>
</Packet>
"""


class AE200Error(RuntimeError):
    """Base exception for AE-200 communication errors."""


class AE200ConnectionError(AE200Error):
    """Raised when the controller cannot be reached."""


class AE200ProtocolError(AE200Error):
    """Raised when the controller returns invalid or unusable data."""


class AE200WriteError(AE200Error):
    """Raised when a write is rejected or cannot be verified."""


@dataclass(frozen=True, slots=True)
class AE200Group:
    """One group discovered from the controller."""

    group_id: str
    name: str
    discovery_attributes: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AE200StatusResult:
    """Parsed status response."""

    statuses: Mapping[str, Mapping[str, str]]
    errors: tuple[Mapping[str, str], ...] = ()
    command: str = ""
    raw_response: str = ""


def clean_host(value: str) -> str:
    """Return a host[:port] value suitable for the AE-200 URL."""

    candidate = value.strip()
    if not candidate:
        raise AE200ProtocolError("The controller host is empty")

    if "://" not in candidate:
        candidate = f"http://{candidate}"

    parsed = urlparse(candidate)
    host = parsed.netloc or parsed.path
    host = host.split("/")[0].strip()
    if not host or any(character.isspace() for character in host):
        raise AE200ProtocolError("The controller host is invalid")
    return host


def build_status_request(
    group_ids: Iterable[str],
    attributes: Iterable[str] = STATUS_ATTRIBUTES,
) -> str:
    """Build one batched, read-only status request."""

    root = ET.Element("Packet")
    ET.SubElement(root, "Command").text = "getRequest"
    database = ET.SubElement(root, "DatabaseManager")

    requested_attributes: dict[str, str] = {}
    for attribute in attributes:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]*", attribute):
            raise AE200ProtocolError(f"Invalid status attribute: {attribute!r}")
        if attribute == "Group":
            continue
        requested_attributes[attribute] = "*"

    count = 0
    for raw_group_id in group_ids:
        group_id = str(raw_group_id).strip()
        if not group_id:
            raise AE200ProtocolError("A group ID is empty")
        ET.SubElement(
            database,
            "Mnet",
            {"Group": group_id, **requested_attributes},
        )
        count += 1

    if count == 0:
        raise AE200ProtocolError("No groups were supplied")

    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _normalise_write_value(attribute: str, value: object) -> str:
    text = str(value).strip().upper()

    if attribute == ATTR_DRIVE:
        if text not in {"ON", "OFF"}:
            raise AE200WriteError(f"Unsupported power value: {value!r}")
        return text

    if attribute == ATTR_MODE:
        allowed = {
            *AUTO_RAW_MODES,
            RAW_MODE_COOL,
            RAW_MODE_HEAT,
            RAW_MODE_DRY,
            RAW_MODE_FAN,
        }
        if text not in allowed:
            raise AE200WriteError(f"Unsupported mode value: {value!r}")
        return text

    if attribute == ATTR_FAN_SPEED:
        if text not in KNOWN_FAN_MODES:
            raise AE200WriteError(f"Unsupported fan value: {value!r}")
        return text

    if attribute == ATTR_AIR_DIRECTION:
        if text not in KNOWN_AIR_DIRECTIONS:
            raise AE200WriteError(
                f"Unsupported air-direction value: {value!r}"
            )
        return text

    if attribute == ATTR_SET_TEMP:
        try:
            number = float(str(value))
        except (TypeError, ValueError) as exc:
            raise AE200WriteError(
                f"Invalid temperature value: {value!r}"
            ) from exc
        if not 5.0 <= number <= 40.0:
            raise AE200WriteError(
                f"Temperature {number:g} °C is outside the protocol safety range"
            )
        return f"{number:g}"

    raise AE200WriteError(f"Attribute {attribute!r} is not writable")


def build_set_request(
    group_id: str,
    attributes: Mapping[str, object],
) -> tuple[str, dict[str, str]]:
    """Build a write request for exactly one group."""

    target = str(group_id).strip()
    if not target:
        raise AE200WriteError("The target group ID is empty")
    if not attributes:
        raise AE200WriteError("No attributes were supplied")

    normalised: dict[str, str] = {}
    for key, value in attributes.items():
        if key not in WRITABLE_ATTRIBUTES:
            raise AE200WriteError(f"Attribute {key!r} is not writable")
        normalised[key] = _normalise_write_value(key, value)

    root = ET.Element("Packet")
    ET.SubElement(root, "Command").text = "setRequest"
    database = ET.SubElement(root, "DatabaseManager")
    ET.SubElement(database, "Mnet", {"Group": target, **normalised})

    payload = ET.tostring(root, encoding="unicode", xml_declaration=True)

    # Defensive invariant: every write must address exactly one Mnet node.
    parsed = ET.fromstring(payload)
    nodes = parsed.findall("./DatabaseManager/Mnet")
    if len(nodes) != 1 or nodes[0].get("Group") != target:
        raise AE200WriteError("Unsafe write payload generated")

    return payload, normalised


def parse_discovery(xml_text: str) -> dict[str, AE200Group]:
    """Parse group discovery XML."""

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise AE200ProtocolError("Discovery response is not valid XML") from exc

    groups: dict[str, AE200Group] = {}
    for node in root.findall(".//MnetRecord"):
        group_id = (node.get("Group") or "").strip()
        if not group_id:
            continue
        name = (
            node.get("GroupNameWeb")
            or node.get("GroupName")
            or f"Group {group_id}"
        ).strip()
        groups[group_id] = AE200Group(
            group_id=group_id,
            name=name,
            discovery_attributes=dict(node.attrib),
        )

    if not groups:
        raise AE200ProtocolError("The controller returned no Mnet groups")
    return groups


def parse_status(xml_text: str) -> AE200StatusResult:
    """Parse an AE-200 status response, preserving protocol errors."""

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise AE200ProtocolError("Status response is not valid XML") from exc

    command = (root.findtext("./Command") or "").strip()
    statuses: dict[str, dict[str, str]] = {}
    for node in root.findall(".//Mnet"):
        group_id = (node.get("Group") or "").strip()
        if group_id:
            statuses[group_id] = dict(node.attrib)

    errors = tuple(dict(node.attrib) for node in root.findall(".//ERROR"))
    if not statuses:
        message = "; ".join(
            f"{error.get('Point', '?')}: {error.get('Message', 'error')}"
            for error in errors
        )
        raise AE200ProtocolError(
            "The controller returned no status records"
            + (f" ({message})" if message else "")
        )

    return AE200StatusResult(
        statuses=statuses,
        errors=errors,
        command=command,
        raw_response=xml_text,
    )


class AE200Client:
    """Asynchronous AE-200 protocol client using Home Assistant's session."""

    def __init__(
        self,
        host: str,
        session: ClientSession,
        timeout: float = 8.0,
    ) -> None:
        self.host = clean_host(host)
        self.session = session
        self.timeout = max(2.0, float(timeout))
        self.websocket_url = f"ws://{self.host}/b_xmlproc/"
        self.origin = f"http://{self.host}"

    def _connect(self):
        return self.session.ws_connect(
            self.websocket_url,
            protocols=("b_xmlproc",),
            origin=self.origin,
            compress=0,
            heartbeat=None,
            timeout=ClientWSTimeout(
                ws_receive=self.timeout,
                ws_close=2.0,
            ),
            max_msg_size=0,
        )

    async def _read_exchange(self, payload: str) -> str:
        try:
            async with self._connect() as websocket:
                await asyncio.wait_for(
                    websocket.send_str(payload),
                    timeout=self.timeout,
                )
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=self.timeout,
                )
        except asyncio.CancelledError:
            raise
        except (TimeoutError, OSError, ClientError) as exc:
            raise AE200ConnectionError(
                f"Unable to communicate with AE-200 at {self.host}: {exc}"
            ) from exc

        if message.type == WSMsgType.TEXT:
            return str(message.data)
        if message.type == WSMsgType.BINARY:
            return bytes(message.data).decode("utf-8", errors="replace")
        if message.type == WSMsgType.ERROR:
            raise AE200ConnectionError(
                f"AE-200 WebSocket failed: {websocket.exception()}"
            )
        raise AE200ProtocolError(
            f"AE-200 closed before returning XML (frame type {message.type})"
        )

    async def async_discover_groups(self) -> dict[str, AE200Group]:
        """Discover all configured Mnet groups."""

        return parse_discovery(await self._read_exchange(DISCOVERY_REQUEST))

    async def async_get_status(
        self,
        group_ids: Iterable[str],
    ) -> AE200StatusResult:
        """Read one or more groups in a single request."""

        payload = build_status_request(group_ids)
        return parse_status(await self._read_exchange(payload))

    async def async_set_attributes(
        self,
        group_id: str,
        attributes: Mapping[str, object],
    ) -> Mapping[str, str]:
        """Write changed attributes to exactly one group.

        Some AE-200 firmware closes without returning a set response. A clean
        close or short response timeout is therefore accepted; definitive
        success is established by the coordinator's selected-group read-back.
        """

        payload, normalised = build_set_request(group_id, attributes)
        try:
            async with self._connect() as websocket:
                await asyncio.wait_for(
                    websocket.send_str(payload),
                    timeout=self.timeout,
                )

                try:
                    message = await asyncio.wait_for(
                        websocket.receive(),
                        timeout=min(0.75, self.timeout / 2),
                    )
                except TimeoutError:
                    message = None

                if message is not None and message.type in {
                    WSMsgType.TEXT,
                    WSMsgType.BINARY,
                }:
                    response = (
                        str(message.data)
                        if message.type == WSMsgType.TEXT
                        else bytes(message.data).decode(
                            "utf-8", errors="replace"
                        )
                    )
                    try:
                        root = ET.fromstring(response)
                    except ET.ParseError:
                        root = None
                    if root is not None:
                        command = (root.findtext("./Command") or "").strip()
                        errors = [
                            dict(node.attrib)
                            for node in root.findall(".//ERROR")
                        ]
                        if (
                            command in {"setErrorResponse", "getErrorResponse"}
                            or errors
                        ):
                            details = "; ".join(
                                f"{item.get('Point', '?')}: "
                                f"{item.get('Message', item.get('Code', 'error'))}"
                                for item in errors
                            )
                            raise AE200WriteError(
                                details or f"Controller returned {command}"
                            )
                elif message is not None and message.type == WSMsgType.ERROR:
                    raise AE200ConnectionError(
                        f"AE-200 WebSocket failed: {websocket.exception()}"
                    )
                # CLOSE/CLOSING/CLOSED are accepted here; read-back verifies.
        except asyncio.CancelledError:
            raise
        except AE200WriteError:
            raise
        except (TimeoutError, OSError, ClientError) as exc:
            raise AE200ConnectionError(
                f"Unable to write to AE-200 at {self.host}: {exc}"
            ) from exc

        return normalised


def values_match(attribute: str, expected: object, actual: object) -> bool:
    """Compare requested and returned values."""

    if attribute == ATTR_SET_TEMP:
        try:
            return abs(float(str(expected)) - float(str(actual))) < 0.06
        except (TypeError, ValueError):
            return False

    expected_text = str(expected).strip().upper()
    actual_text = str(actual).strip().upper()

    if attribute == ATTR_MODE and expected_text in AUTO_RAW_MODES:
        return actual_text in AUTO_RAW_MODES

    return expected_text == actual_text
