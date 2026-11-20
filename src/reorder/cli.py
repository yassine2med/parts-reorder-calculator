"""Command line entry for the parts reorder calculator."""

from __future__ import annotations

import argparse
import csv
import sys

from .core import DataError, calculate, load_parts


def main(argv: list[str] | None = None) -> int:
    """Return 0 when nothing needs ordering, 1 when orders are needed, 2 on bad input."""
    parser = argparse.ArgumentParser(prog="reorder", description="Min/max reorder calculator")
    sub = parser.add_subparsers(dest="command", required=True)
    calc = sub.add_parser("calc", help="calculate reorder points and order quantities")
    calc.add_argument("file", help="parts CSV")
    calc.add_argument("--review-days", type=float, default=14, help="days of demand above the reorder point (default 14)")
    calc.add_argument("--only-orders", action="store_true", help="hide parts that need nothing")
    calc.add_argument("--out", help="also write the full result to this CSV")
    args = parser.parse_args(argv)
    if args.review_days < 0:
        print("Bad input: --review-days cannot be negative", file=sys.stderr)
        return 2
    try:
        parts = load_parts(args.file)
    except FileNotFoundError:
        print(f"File not found: {args.file}", file=sys.stderr)
        return 2
    except DataError as exc:
        print(f"Bad input: {exc}", file=sys.stderr)
        return 2
    results = [calculate(p, args.review_days) for p in parts]
    print(f"{'part':<9}{'on hand':>8}{'on ord':>8}{'safety':>8}{'ROP':>8}{'max':>8}{'order':>7}{'cost':>9}  status")
    for r in results:
        if args.only_orders and r.order_qty == 0:
            continue
        print(f"{r.part.part_id:<9}{r.part.on_hand:>8g}{r.part.on_order:>8g}{r.safety_stock:>8.1f}"
              f"{r.reorder_point:>8.1f}{r.max_level:>8.1f}{r.order_qty:>7}{r.order_cost:>9.2f}  {r.status}")
    orders = [r for r in results if r.order_qty > 0]
    total = sum(r.order_cost for r in orders)
    print(f"{len(results)} parts, {len(orders)} to order, total {total:.2f}")
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["part_id", "safety_stock", "reorder_point", "max_level", "order_qty", "order_cost", "status"])
            for r in results:
                w.writerow([r.part.part_id, r.safety_stock, r.reorder_point, r.max_level, r.order_qty, f"{r.order_cost:.2f}", r.status])
    return 1 if orders else 0


if __name__ == "__main__":
    sys.exit(main())
