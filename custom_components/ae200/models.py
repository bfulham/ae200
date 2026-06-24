"""Data models and pure helpers for the Mitsubishi AE-200 integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .const import (
    ATTR_DRIVE,
    ATTR_ERROR_SIGN,
    ATTR_FILTER_SIGN,
    ATTR_MODE,
    ATTR_SCHEDULE,
)
from .protocol import AE200Group


@dataclass(frozen=True, slots=True)
class AE200Data:
    """Coordinator data shared by all entities."""

    groups: Mapping[str, AE200Group]
    statuses: Mapping[str, Mapping[str, str]]
    protocol_errors: tuple[Mapping[str, str], ...] = field(default_factory=tuple)

    @property
    def group_count(self) -> int:
        return len(self.groups)

    @property
    def running_count(self) -> int:
        return sum(
            1
            for status in self.statuses.values()
            if status.get(ATTR_DRIVE, "").upper() == "ON"
        )

    @property
    def fault_count(self) -> int:
        return sum(
            1
            for status in self.statuses.values()
            if status.get(ATTR_ERROR_SIGN, "").upper() not in {"", "OFF", "0"}
        )

    @property
    def filter_alert_count(self) -> int:
        return sum(
            1
            for status in self.statuses.values()
            if status.get(ATTR_FILTER_SIGN, "").upper() == "ON"
        )

    @property
    def scheduled_count(self) -> int:
        return sum(
            1
            for status in self.statuses.values()
            if status.get(ATTR_SCHEDULE, "").upper() == "ON"
        )

    @property
    def raw_modes(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    status.get(ATTR_MODE, "").upper()
                    for status in self.statuses.values()
                    if status.get(ATTR_MODE)
                }
            )
        )


def as_float(value: object) -> float | None:
    """Convert a controller value to float when meaningful."""

    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"*", "--"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def is_on_value(value: object) -> bool:
    """Interpret common AE-200 on/active values."""

    return str(value or "").strip().upper() in {
        "ON",
        "ENABLE",
        "ENABLED",
        "PERMIT",
        "ACTIVE",
        "YES",
        "1",
    }


def is_problem_value(value: object) -> bool:
    """Interpret AE-200 fault-like values."""

    return str(value or "").strip().upper() not in {
        "",
        "OFF",
        "NONE",
        "NORMAL",
        "NO",
        "0",
        "*",
        "--",
    }
