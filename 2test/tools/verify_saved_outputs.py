"""无需重跑优化，独立复核已保存的Excel、CSV和PDF输出。"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import openpyxl
from pypdf import PdfReader


BASE = Path(__file__).resolve().parents[1]


def _number(value) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise AssertionError(f"发现非有限数值: {value}")
    return number


def main() -> None:
    payload = json.loads((BASE / "outputs/excel_payload.json").read_text(encoding="utf-8"))
    wb = openpyxl.load_workbook(BASE / "result2.xlsx", read_only=False, data_only=True)
    assert wb.sheetnames == ["计划购电量", "充放电量", "紧急购电量"]
    plan, battery, emergency = (wb[name] for name in wb.sheetnames)
    assert (plan.max_row, plan.max_column) == (335, 147)
    assert battery.max_row - 1 == len(payload["battery_rows"]) == 2004
    assert emergency.max_row - 1 == len(payload["emergency_rows"])

    max_error = 0.0
    for r, expected in enumerate(payload["plan_values"], 2):
        actual = [_number(plan.cell(r, c).value) for c in range(2, 148)]
        max_error = max(max_error, max(abs(a-b) for a,b in zip(actual, expected)))
    for r, expected in enumerate(payload["battery_rows"], 2):
        actual_date = battery.cell(r,1).value
        if isinstance(actual_date, datetime): actual_date = actual_date.date().isoformat()
        assert str(actual_date) == expected["date"] and battery.cell(r,2).value == expected["time_range"]
        assert (battery.cell(r,5).value or "") == expected["time"]
        numeric = [_number(battery.cell(r,c).value) for c in (3,4)]
        wanted = [expected["charge_kwh"], expected["discharge_kwh"]]
        if expected["soc_kwh"] == "":
            assert battery.cell(r,6).value is None
        else:
            numeric.append(_number(battery.cell(r,6).value))
            wanted.append(expected["soc_kwh"])
        max_error = max(max_error, max(abs(a-b) for a,b in zip(numeric,wanted)))
    for r, expected in enumerate(payload["emergency_rows"], 2):
        actual_date = emergency.cell(r,1).value
        if isinstance(actual_date, datetime): actual_date = actual_date.date().isoformat()
        assert str(actual_date) == expected["date"] and emergency.cell(r,2).value == expected["time_range"]
        max_error = max(max_error, abs(_number(emergency.cell(r,3).value)-expected["emergency_kwh"]))
    wb.close()
    assert max_error <= 1e-7

    pdfs = sorted((BASE / "figures").glob("problem2_*.pdf"))
    assert len(pdfs) == 3
    for path in pdfs:
        reader = PdfReader(path)
        assert len(reader.pages) == 1 and path.stat().st_size > 3000
        assert not reader.pages[0].get("/Resources", {}).get("/XObject")

    validation_path = BASE / "outputs/validation.json"
    checks = json.loads(validation_path.read_text(encoding="utf-8"))
    checks.update({
        "excel_plan_max_abs_error": max_error,
        "excel_plan_rows": plan.max_row - 1,
        "excel_battery_rows": battery.max_row - 1,
        "excel_emergency_rows": emergency.max_row - 1,
        "excel_sheet_names_preserved": True,
        "vector_pdf_count": len(pdfs),
    })
    validation_path.write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"PASS", "max_output_error":max_error, "pdf_count":len(pdfs)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
