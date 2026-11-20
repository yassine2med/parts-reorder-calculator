import pytest

from reorder.cli import main
from reorder.core import DataError, Part, calculate, load_parts, safety_stock


def part(**kw):
    base = dict(part_id="P", description="d", avg_daily_use=2, max_daily_use=4, lead_time_days=5,
                max_lead_time_days=10, on_hand=0, on_order=0, unit_cost=2.0, order_multiple=1)
    base.update(kw)
    return Part(**base)


def test_safety_stock():
    assert safety_stock(part()) == 4 * 10 - 2 * 5


def test_safety_stock_never_negative():
    assert safety_stock(part(max_daily_use=1, max_lead_time_days=1)) == 0


def test_reorder_point():
    assert calculate(part()).reorder_point == 2 * 5 + 30


def test_max_level_uses_review_days():
    assert calculate(part(), review_days=10).max_level == 40 + 2 * 10


def test_order_quantity_reaches_max():
    r = calculate(part(on_hand=10), review_days=14)
    assert r.order_qty == 68 - 10 and r.status == "REORDER"


def test_order_rounds_up_to_multiple():
    r = calculate(part(on_hand=10, order_multiple=12), review_days=14)
    assert r.order_qty == 60


def test_no_order_above_reorder_point():
    r = calculate(part(on_hand=100))
    assert r.order_qty == 0 and r.status == "OK"


def test_on_order_counts_toward_position():
    r = calculate(part(on_hand=10, on_order=100))
    assert r.order_qty == 0 and r.status == "ON ORDER"


def test_stockout_status():
    assert calculate(part(on_hand=0)).status == "STOCKOUT"


def test_order_cost():
    r = calculate(part(on_hand=10, unit_cost=2.5))
    assert r.order_cost == r.order_qty * 2.5


def test_load_example():
    parts = load_parts("examples/parts.csv")
    assert len(parts) == 6 and parts[0].part_id == "FLT-2020"


def test_missing_column(tmp_path):
    p = tmp_path / "p.csv"
    p.write_text("part_id,description\nA,b\n")
    with pytest.raises(DataError, match="missing column"):
        load_parts(str(p))


def test_max_below_average_rejected(tmp_path):
    p = tmp_path / "p.csv"
    p.write_text("part_id,description,avg_daily_use,max_daily_use,lead_time_days,max_lead_time_days,on_hand,on_order,unit_cost,order_multiple\nA,b,5,1,1,1,0,0,1,1\n")
    with pytest.raises(DataError, match="max_daily_use"):
        load_parts(str(p))


def test_cli_exit_codes(capsys):
    assert main(["calc", "examples/parts.csv"]) == 1
    assert "STOCKOUT" in capsys.readouterr().out
    assert main(["calc", "missing.csv"]) == 2


def test_cli_only_orders_and_csv(capsys, tmp_path):
    out = tmp_path / "o.csv"
    main(["calc", "examples/parts.csv", "--only-orders", "--out", str(out)])
    text = capsys.readouterr().out
    assert "LMP-T8" not in text
    assert out.read_text().splitlines()[0].startswith("part_id,safety_stock")
