"""Min/max reorder point math for maintenance parts."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass

REQUIRED = [
    "part_id", "description", "avg_daily_use", "max_daily_use", "lead_time_days",
    "max_lead_time_days", "on_hand", "on_order", "unit_cost", "order_multiple",
]


class DataError(ValueError):
    """Raised for a bad CSV value."""


@dataclass(frozen=True)
class Part:
    part_id: str
    description: str
    avg_daily_use: float
    max_daily_use: float
    lead_time_days: float
    max_lead_time_days: float
    on_hand: float
    on_order: float
    unit_cost: float
    order_multiple: int


@dataclass(frozen=True)
class Result:
    part: Part
    safety_stock: float
    reorder_point: float
    max_level: float
    position: float
    order_qty: int
    status: str

    @property
    def order_cost(self) -> float:
        return self.order_qty * self.part.unit_cost


def safety_stock(part: Part) -> float:
    """Worst case demand over the worst case lead time minus the normal demand."""
    return max(0.0, part.max_daily_use * part.max_lead_time_days - part.avg_daily_use * part.lead_time_days)


def calculate(part: Part, review_days: float = 14) -> Result:
    """Reorder point = lead time demand + safety stock; max = reorder point + review period demand.

    Inventory position is on hand plus on order. When it is at or below the
    reorder point, the order quantity brings it up to max, rounded up to the
    pack size. Zero stock on hand is reported as STOCKOUT.
    """
    ss = safety_stock(part)
    rop = part.avg_daily_use * part.lead_time_days + ss
    max_level = rop + part.avg_daily_use * review_days
    position = part.on_hand + part.on_order
    qty = 0
    if position <= rop:
        need = max_level - position
        qty = int(math.ceil(need / part.order_multiple) * part.order_multiple)
    if part.on_hand <= 0:
        status = "STOCKOUT"
    elif qty > 0:
        status = "REORDER"
    elif part.on_hand <= rop:
        status = "ON ORDER"
    else:
        status = "OK"
    return Result(part, round(ss, 2), round(rop, 2), round(max_level, 2), position, qty, status)


def _num(row: dict, key: str, line: int) -> float:
    raw = (row.get(key) or "").strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise DataError(f"line {line}: '{key}' must be a number, got '{raw}'") from exc
    if value < 0:
        raise DataError(f"line {line}: '{key}' cannot be negative")
    return value


def load_parts(path: str) -> list[Part]:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise DataError(f"missing column(s): {', '.join(missing)}")
        rows = list(reader)
    parts, seen = [], set()
    for i, row in enumerate(rows, start=2):
        pid = (row["part_id"] or "").strip()
        if not pid:
            raise DataError(f"line {i}: part_id is empty")
        if pid in seen:
            raise DataError(f"line {i}: duplicate part_id '{pid}'")
        seen.add(pid)
        mult = _num(row, "order_multiple", i)
        if mult < 1 or mult != int(mult):
            raise DataError(f"line {i}: 'order_multiple' must be a whole number of 1 or more")
        if _num(row, "max_daily_use", i) < _num(row, "avg_daily_use", i):
            raise DataError(f"line {i}: max_daily_use is below avg_daily_use")
        if _num(row, "max_lead_time_days", i) < _num(row, "lead_time_days", i):
            raise DataError(f"line {i}: max_lead_time_days is below lead_time_days")
        parts.append(Part(
            pid, row["description"].strip(), _num(row, "avg_daily_use", i), _num(row, "max_daily_use", i),
            _num(row, "lead_time_days", i), _num(row, "max_lead_time_days", i), _num(row, "on_hand", i),
            _num(row, "on_order", i), _num(row, "unit_cost", i), int(mult),
        ))
    return parts
