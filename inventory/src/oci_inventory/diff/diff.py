from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .hash import stable_record_hash


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            recs.append(json.loads(line))
    return recs


def _index_by_ocid(records: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by: Dict[str, Dict[str, Any]] = {}
    for r in records:
        ocid = str(r.get("ocid") or "")
        if not ocid:
            # skip malformed records
            continue
        by[ocid] = r
    return by


def compute_diff(
    prev_records: Iterable[Dict[str, Any]],
    curr_records: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute diff between two sets of normalized records.
    Returns a structure containing:
      - added/removed/changed/unchanged as lists of OCIDs
      - details mapping OCID->{prev_hash?, curr_hash?}
      - summary counts
    """
    prev_by = _index_by_ocid(prev_records)
    curr_by = _index_by_ocid(curr_records)

    added: List[str] = []
    removed: List[str] = []
    changed: List[str] = []
    unchanged: List[str] = []
    details: Dict[str, Dict[str, str]] = {}

    prev_ocids = set(prev_by.keys())
    curr_ocids = set(curr_by.keys())

    for ocid in sorted(prev_ocids - curr_ocids):
        prev_h = stable_record_hash(prev_by[ocid])
        removed.append(ocid)
        details[ocid] = {"prev_hash": prev_h}

    for ocid in sorted(curr_ocids - prev_ocids):
        curr_h = stable_record_hash(curr_by[ocid])
        added.append(ocid)
        details[ocid] = {"curr_hash": curr_h}

    for ocid in sorted(prev_ocids & curr_ocids):
        prev_h = stable_record_hash(prev_by[ocid])
        curr_h = stable_record_hash(curr_by[ocid])
        if prev_h != curr_h:
            changed.append(ocid)
            details[ocid] = {"prev_hash": prev_h, "curr_hash": curr_h}
        else:
            unchanged.append(ocid)
            details[ocid] = {"prev_hash": prev_h, "curr_hash": curr_h}

    summary = {
        "added": len(added),
        "removed": len(removed),
        "changed": len(changed),
        "unchanged": len(unchanged),
        "prev_total": len(prev_by),
        "curr_total": len(curr_by),
    }

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
        "details": details,
        "summary": summary,
    }


def diff_files(prev_path: Path, curr_path: Path) -> Dict[str, Any]:
    prev = _load_jsonl(prev_path)
    curr = _load_jsonl(curr_path)
    return compute_diff(prev, curr)


def write_diff(outdir: Path, diff_obj: Dict[str, Any]) -> Tuple[Path, Path]:
    """
    Write diff.json and diff_summary.json to outdir, returning their paths.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    diff_path = outdir / "diff.json"
    summary_path = outdir / "diff_summary.json"
    diff_path.write_text(json.dumps(diff_obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False), encoding="utf-8")
    summary_path.write_text(json.dumps(diff_obj.get("summary", {}), sort_keys=True, separators=(',', ':'), ensure_ascii=False), encoding="utf-8")
    return diff_path, summary_path