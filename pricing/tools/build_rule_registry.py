#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    rows = []
    if not path.exists():
      return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return value or "unknown"


def normalize_service_name(text: str) -> str:
    value = " ".join(str(text or "").split()).strip(" -")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"^Oracle PaaS and IaaS Universal Credits$", "", value, flags=re.I).strip()
    return value


def is_garbage_service_name(text: str) -> bool:
    value = normalize_service_name(text)
    if not value:
        return True
    if re.match(r"^[\d.\- ]+$", value):
        return True
    if re.match(r"^(minimum|notes|part|capacity per|per month|per hour|invocations|limited to|over \d|first \d)", value, re.I):
        return True
    if len(value) < 6:
        return True
    return False


def extract_service_name_from_line(line: str) -> str:
    value = str(line or "").strip()
    if not re.match(r"^B\d{5,}\b", value):
        return ""
    value = re.sub(r"^B\d{5,}\s+", "", value)
    for marker in [
        " Currency Unit",
        " OCPU Per Hour",
        " ECPU Per Hour",
        " GPU Per Hour",
        " Port Hour",
        " Load Balancer Hour",
        " Load Balancer",
        " Mbps Per Hour",
        " Request -",
        " Requests -",
        " Requests ",
        " User Per Month",
        " Named User",
        " Node Per Hour",
        " Each ",
        " Gigabyte Storage",
        " Gigabyte Per",
        " Terabyte Storage",
        " Hosted Environment",
        " Desktop Per Month",
        " Token",
        " Minute of Output",
        " HeatWave",
        " NVMe ",
        " Consumer User",
        " Workforce User",
    ]:
        if marker in value:
            value = value.split(marker, 1)[0]
            break
    value = normalize_service_name(value)
    return "" if is_garbage_service_name(value) else value


def pick_service_name(*candidates: str) -> str:
    for item in candidates:
        value = normalize_service_name(item)
        if not is_garbage_service_name(value):
            return value
    return "Unknown Service"


def classify_note(line: str) -> str:
    lower = line.lower()
    if "minimum service period" in lower:
        return "minimum_service_period"
    if "billed per second" in lower or "one-minute minimum" in lower:
        return "billing_granularity"
    if "free tier" in lower:
        return "free_tier"
    if "increments of" in lower or "must be purchased in increments" in lower:
        return "increment_rule"
    if "includes entitlement" in lower or lower.startswith("includes:"):
        return "entitlement"
    if "subject to byol" in lower or "byol" in lower:
        return "byol"
    if "cannot be purchased" in lower:
        return "purchase_restriction"
    if "requires a minimum" in lower or "minimum of" in lower:
        return "minimum_quantity"
    if "total enabled" in lower or "cannot exceed" in lower:
        return "maximum_limit"
    return "general_note"


def extract_part_numbers(text: str) -> list[str]:
    return sorted(set(re.findall(r"\bB\d{5,}\b", str(text or ""))))


def clean_bullets(bullets: list[str]) -> list[str]:
    cleaned = []
    for bullet in bullets or []:
        value = bullet.strip()
        if not value or value == "-":
            continue
        cleaned.append(value)
    return cleaned


def build_registry(extract_dir: Path) -> dict:
    summary = read_json(extract_dir / "summary.json")
    prereqs = read_jsonl(extract_dir / "combined" / "prerequisites.jsonl")
    notes = read_jsonl(extract_dir / "combined" / "notes.jsonl")
    mentions = read_jsonl(extract_dir / "combined" / "part_mentions.jsonl")

    services: dict[str, dict] = {}
    parts: dict[str, dict] = {}
    prerequisite_rules = []
    billing_rules = []

    def ensure_service(name: str) -> dict:
        display = pick_service_name(name)
        key = slugify(display)
        if key not in services:
            services[key] = {
                "id": key,
                "name": display,
                "prerequisites": [],
                "notes": [],
                "parts": [],
                "sources": [],
            }
        return services[key]

    def ensure_part(part_number: str) -> dict:
        if part_number not in parts:
            parts[part_number] = {
                "part_number": part_number,
                "service_ids": [],
                "notes": [],
                "prerequisites": [],
                "mentions": [],
            }
        return parts[part_number]

    for row in mentions:
        service_name = pick_service_name(
            extract_service_name_from_line(row.get("line", "")),
            row.get("service_context", ""),
        )
        service = ensure_service(service_name)
        service["sources"].append({"pdf": row["source_pdf"], "page": row["page"]})
        for part_number in row.get("parts", []):
            if part_number not in service["parts"]:
                service["parts"].append(part_number)
            part = ensure_part(part_number)
            if service["id"] not in part["service_ids"]:
                part["service_ids"].append(service["id"])
            part["mentions"].append({
                "pdf": row["source_pdf"],
                "page": row["page"],
                "line": row["line"],
            })

    for row in prereqs:
        service = ensure_service(pick_service_name(row.get("service_context", ""), row.get("trigger_line", "")))
        bullets = clean_bullets(row.get("bullets", []))
        record = {
            "pdf": row["source_pdf"],
            "page": row["page"],
            "trigger_line": row["trigger_line"],
            "bullets": bullets,
            "part_numbers": extract_part_numbers(" ".join(bullets)),
        }
        prerequisite_rules.append({
            "service_id": service["id"],
            **record,
        })
        service["prerequisites"].append(record)
        service["sources"].append({"pdf": row["source_pdf"], "page": row["page"]})
        for part_number in record["part_numbers"]:
            part = ensure_part(part_number)
            part["prerequisites"].append({
                "service_id": service["id"],
                "pdf": row["source_pdf"],
                "page": row["page"],
                "trigger_line": row["trigger_line"],
            })

    for row in notes:
        service = ensure_service(pick_service_name(row.get("service_context", ""), row.get("line", "")))
        note_type = classify_note(row["line"])
        record = {
            "pdf": row["source_pdf"],
            "page": row["page"],
            "type": note_type,
            "line": row["line"],
            "part_numbers": extract_part_numbers(row["line"]),
        }
        billing_rules.append({
            "service_id": service["id"],
            **record,
        })
        service["notes"].append(record)
        service["sources"].append({"pdf": row["source_pdf"], "page": row["page"]})
        for part_number in record["part_numbers"]:
            part = ensure_part(part_number)
            part["notes"].append({
                "service_id": service["id"],
                "pdf": row["source_pdf"],
                "page": row["page"],
                "type": note_type,
                "line": row["line"],
            })

    for service in services.values():
        service["parts"].sort()
        service["sources"] = sorted(
            { (item["pdf"], item["page"]) for item in service["sources"] }
        )
        service["sources"] = [{"pdf": pdf, "page": page} for pdf, page in service["sources"]]

    for part in parts.values():
        part["service_ids"] = sorted({
            service_id
            for service_id in part["service_ids"]
            if service_id in services and services[service_id]["name"] != "Unknown Service"
        })

    registry = {
        "metadata": {
            "source_summary": summary,
            "service_count": len(services),
            "part_count": len(parts),
            "prerequisite_rule_count": len(prerequisite_rules),
            "billing_rule_count": len(billing_rules),
        },
        "services": dict(sorted(services.items())),
        "parts": dict(sorted(parts.items())),
        "rules": {
            "prerequisites": prerequisite_rules,
            "billing": billing_rules,
        },
    }
    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized OCI rule registry from extracted PDF artifacts.")
    parser.add_argument("--extract-dir", required=True, type=Path)
    parser.add_argument("--out-file", required=True, type=Path)
    args = parser.parse_args()

    registry = build_registry(args.extract_dir)
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(registry, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
