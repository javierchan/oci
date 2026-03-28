#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import xlrd


PRICE_SHEET = "Oracle PaaS and IaaS Price List"
SUPPLEMENT_SHEET = "Oracle PaaS and IaaS Supplement"


def cell_str(sheet: xlrd.sheet.Sheet, rowx: int, colx: int) -> str:
    if colx >= sheet.ncols:
        return ""
    value = sheet.cell_value(rowx, colx)
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def find_price_header(sheet: xlrd.sheet.Sheet) -> int:
    for rowx in range(sheet.nrows):
        row = [cell_str(sheet, rowx, colx) for colx in range(sheet.ncols)]
        if "Part\nNumber" in row and "Metric" in row and "Additional Information" in row:
            return rowx
    raise RuntimeError("Could not find header row in price list sheet")


def find_supplement_header(sheet: xlrd.sheet.Sheet) -> int:
    for rowx in range(sheet.nrows):
        row = [cell_str(sheet, rowx, colx) for colx in range(sheet.ncols)]
        if "Part\nNumber" in row and "SUBSCRIPTION SERVICE" in row and "ADDITIONAL REQUIREMENTS AND PREREQUISITES" in row:
            return rowx
    raise RuntimeError("Could not find header row in supplement sheet")


def maybe_float(text: str):
    value = text.strip()
    if not value or value in {"-", "Free Tier"}:
        return None
    normalized = value.replace(",", "")
    try:
        return float(normalized)
    except ValueError:
        return None


def clean_text(text: str) -> str:
    value = " ".join(str(text or "").split())
    return value.strip()


def extract_prerequisites(text: str) -> list[str]:
    value = clean_text(text)
    if not value:
        return []
    match = re.search(r"Requires as a prerequisite:\s*(.+)$", value, re.I)
    if not match:
        return []
    tail = match.group(1).strip().rstrip(".")
    parts = [item.strip(" .;") for item in re.split(r";|,(?=\s*Oracle\b)|\band\b", tail) if item.strip(" .;")]
    return parts


def extract_price_rows(sheet: xlrd.sheet.Sheet, header_rowx: int) -> list[dict]:
    rows = []
    for rowx in range(header_rowx + 1, sheet.nrows):
        part_number = clean_text(cell_str(sheet, rowx, 32))
        service_name = clean_text(cell_str(sheet, rowx, 2))
        metric = clean_text(cell_str(sheet, rowx, 18))
        if not part_number and not service_name:
            continue
        if not re.fullmatch(r"B\d{5,}", part_number):
            continue
        row = {
            "row_index": rowx,
            "part_number": part_number,
            "subscription_service": service_name,
            "metric": metric,
            "metric_minimum": clean_text(cell_str(sheet, rowx, 22)),
            "additional_information": clean_text(cell_str(sheet, rowx, 24)),
            "notes": clean_text(cell_str(sheet, rowx, 30)),
            "universal_credits_paygo": maybe_float(cell_str(sheet, rowx, 14)),
            "annual_flex": maybe_float(cell_str(sheet, rowx, 16)),
            "localized_paygo_price": maybe_float(cell_str(sheet, rowx, 35)),
            "localized_annual_flex_price": maybe_float(cell_str(sheet, rowx, 36)),
            "raw_nonempty_cells": {
                str(colx): clean_text(cell_str(sheet, rowx, colx))
                for colx in range(sheet.ncols)
                if clean_text(cell_str(sheet, rowx, colx))
            },
        }
        rows.append(row)
    return rows


def extract_supplement_rows(sheet: xlrd.sheet.Sheet, header_rowx: int) -> list[dict]:
    rows = []
    for rowx in range(header_rowx + 1, sheet.nrows):
        part_number = clean_text(cell_str(sheet, rowx, 1))
        service_name = clean_text(cell_str(sheet, rowx, 2))
        metric = clean_text(cell_str(sheet, rowx, 3))
        if not part_number and not service_name and not metric:
            continue
        if not re.fullmatch(r"B\d{5,}", part_number):
            continue
        additional = clean_text(cell_str(sheet, rowx, 5))
        row = {
            "row_index": rowx,
            "part_number": part_number,
            "subscription_service": service_name,
            "metric": metric,
            "included_with_subscription_service": clean_text(cell_str(sheet, rowx, 4)),
            "additional_requirements_and_prerequisites": additional,
            "prerequisites": extract_prerequisites(additional),
            "raw_nonempty_cells": {
                str(colx): clean_text(cell_str(sheet, rowx, colx))
                for colx in range(sheet.ncols)
                if clean_text(cell_str(sheet, rowx, colx))
            },
        }
        rows.append(row)
    return rows


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract structured OCI pricing data from localizable XLS workbook.")
    parser.add_argument("--xls-file", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    workbook = xlrd.open_workbook(str(args.xls_file), on_demand=True)
    price_sheet = workbook.sheet_by_name(PRICE_SHEET)
    supplement_sheet = workbook.sheet_by_name(SUPPLEMENT_SHEET)

    price_header = find_price_header(price_sheet)
    supplement_header = find_supplement_header(supplement_sheet)

    price_rows = extract_price_rows(price_sheet, price_header)
    supplement_rows = extract_supplement_rows(supplement_sheet, supplement_header)

    summary = {
        "workbook": args.xls_file.name,
        "sheets": {
            PRICE_SHEET: {
                "rows": price_sheet.nrows,
                "cols": price_sheet.ncols,
                "header_row": price_header,
                "extracted_records": len(price_rows),
            },
            SUPPLEMENT_SHEET: {
                "rows": supplement_sheet.nrows,
                "cols": supplement_sheet.ncols,
                "header_row": supplement_header,
                "extracted_records": len(supplement_rows),
            },
        },
    }

    write_json(args.out_dir / "summary.json", summary)
    write_jsonl(args.out_dir / "price_list_rows.jsonl", price_rows)
    write_jsonl(args.out_dir / "supplement_rows.jsonl", supplement_rows)


if __name__ == "__main__":
    main()
