#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader


PART_RE = re.compile(r"\bB\d{5,}\b")
PAGE_DATE_RE = re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}")
REQUIRES_RE = re.compile(r"Requires as (?:a )?prerequisite[s]?:", re.IGNORECASE)
NOTE_RE = re.compile(
    r"\b("
    r"minimum service period|billed per second|one-minute minimum|free tier|"
    r"requires a minimum|increments of|must be provisioned|"
    r"subject to byol|subject to change|pay as you go pricing not available|"
    r"includes entitlement|cannot be purchased|total enabled|"
    r"standard term length|additional ocpus should be purchased"
    r")\b",
    re.IGNORECASE,
)
HEADER_RE = re.compile(r"^(Part|Number|SUBSCRIPTION SERVICE|Metric|INCLUDED WITH SUBSCRIPTION SERVICE|Prices in US Dollar|Pay as You Go|Oracle PaaS and IaaS Universal Credits)\b", re.IGNORECASE)


@dataclass
class PageRecord:
    page_number: int
    text: str


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_pages(pdf_path: Path) -> list[PageRecord]:
    reader = PdfReader(str(pdf_path))
    pages: list[PageRecord] = []
    for idx, page in enumerate(reader.pages, start=1):
        pages.append(PageRecord(page_number=idx, text=normalize_text(page.extract_text() or "")))
    return pages


def infer_service_context(lines: list[str], hit_index: int) -> str:
    start = max(0, hit_index - 10)
    context_lines = lines[start:hit_index]
    candidates = []
    for line in context_lines:
        if HEADER_RE.search(line):
            continue
        if len(line) < 8:
            continue
        if line.startswith("http"):
            continue
        if "Oracle PaaS and IaaS Universal Credits" in line:
            continue
        if "ADDITIONAL REQUIREMENTS AND PREREQUISITES" in line:
            continue
        if PART_RE.search(line):
            continue
        candidates.append(line)
    if not candidates:
        return ""
    # pick the nearest line that looks like a service title
    return candidates[-1][:300]


def extract_prerequisite_rules(pdf_name: str, pages: list[PageRecord]) -> list[dict]:
    records: list[dict] = []
    for page in pages:
        lines = split_lines(page.text)
        for idx, line in enumerate(lines):
            if not REQUIRES_RE.search(line):
                continue
            service = infer_service_context(lines, idx)
            bullets = []
            for bullet_line in lines[idx + 1: idx + 12]:
                if bullet_line.startswith("-"):
                    bullets.append(bullet_line)
                elif bullets:
                    break
            records.append({
                "source_pdf": pdf_name,
                "page": page.page_number,
                "service_context": service,
                "trigger_line": line,
                "bullets": bullets,
            })
    return records


def extract_note_rules(pdf_name: str, pages: list[PageRecord]) -> list[dict]:
    records: list[dict] = []
    for page in pages:
        lines = split_lines(page.text)
        for idx, line in enumerate(lines):
            if not NOTE_RE.search(line):
                continue
            service = infer_service_context(lines, idx)
            records.append({
                "source_pdf": pdf_name,
                "page": page.page_number,
                "service_context": service,
                "line": line,
            })
    return records


def extract_part_mentions(pdf_name: str, pages: list[PageRecord]) -> list[dict]:
    records: list[dict] = []
    for page in pages:
        lines = split_lines(page.text)
        for idx, line in enumerate(lines):
            parts = sorted(set(PART_RE.findall(line)))
            if not parts:
                continue
            service = infer_service_context(lines, idx)
            records.append({
                "source_pdf": pdf_name,
                "page": page.page_number,
                "parts": parts,
                "line": line[:500],
                "service_context": service,
            })
    return records


def extract_document_meta(pdf_path: Path, pages: list[PageRecord]) -> dict:
    joined = "\n".join(page.text for page in pages[:8])
    return {
        "file_name": pdf_path.name,
        "pages": len(pages),
        "last_updated_mentions": sorted(set(PAGE_DATE_RE.findall(joined))),
        "title_snippet": pages[0].text[:500] if pages else "",
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
            count += 1
    return count


def build_page_payload(pdf_name: str, pages: list[PageRecord]) -> list[dict]:
    return [{"source_pdf": pdf_name, "page": page.page_number, "text": page.text} for page in pages]


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract OCI price list PDFs into structured offline artifacts.")
    parser.add_argument("--price-list", required=True, type=Path)
    parser.add_argument("--supplement", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    docs = {
        "price_list": args.price_list,
        "supplement": args.supplement,
    }

    summary = {"documents": {}, "artifacts": {}}
    all_prereqs: list[dict] = []
    all_notes: list[dict] = []
    all_parts: list[dict] = []

    for key, pdf_path in docs.items():
        pages = extract_pages(pdf_path)
        pdf_dir = args.out_dir / key
        write_json(pdf_dir / "metadata.json", extract_document_meta(pdf_path, pages))
        write_json(pdf_dir / "pages.json", build_page_payload(pdf_path.name, pages))

        prereqs = extract_prerequisite_rules(pdf_path.name, pages)
        notes = extract_note_rules(pdf_path.name, pages)
        parts = extract_part_mentions(pdf_path.name, pages)

        write_jsonl(pdf_dir / "prerequisites.jsonl", prereqs)
        write_jsonl(pdf_dir / "notes.jsonl", notes)
        write_jsonl(pdf_dir / "part_mentions.jsonl", parts)

        summary["documents"][key] = {
            "file_name": pdf_path.name,
            "pages": len(pages),
            "prerequisite_records": len(prereqs),
            "note_records": len(notes),
            "part_mentions": len(parts),
        }
        all_prereqs.extend(prereqs)
        all_notes.extend(notes)
        all_parts.extend(parts)

    summary["artifacts"]["combined_prerequisites"] = write_jsonl(args.out_dir / "combined" / "prerequisites.jsonl", all_prereqs)
    summary["artifacts"]["combined_notes"] = write_jsonl(args.out_dir / "combined" / "notes.jsonl", all_notes)
    summary["artifacts"]["combined_part_mentions"] = write_jsonl(args.out_dir / "combined" / "part_mentions.jsonl", all_parts)

    write_json(args.out_dir / "summary.json", summary)


if __name__ == "__main__":
    main()
