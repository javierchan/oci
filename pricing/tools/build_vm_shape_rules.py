#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "rule-registry" / "vm_shape_rules.json"


def shape(
    shape_name: str,
    kind: str,
    vendor: str,
    family: str,
    series: str,
    *,
    product_label: str | None = None,
    fixed_ocpus: int | None = None,
    fixed_memory_gb: int | None = None,
    ocpu_to_vcpu_ratio: int = 2,
    part_numbers: list[str] | None = None,
    source_notes: list[str] | None = None,
) -> dict:
    aliases = [shape_name]
    if shape_name.startswith("VM."):
        aliases.append(shape_name[3:])
    if shape_name.startswith("BM."):
        aliases.append(shape_name[3:])
    return {
        "shapeName": shape_name,
        "aliases": sorted(set(aliases)),
        "kind": kind,
        "vendor": vendor,
        "family": family,
        "series": series,
        "productLabel": product_label,
        "fixedOcpus": fixed_ocpus,
        "fixedMemoryGb": fixed_memory_gb,
        "ocpuToVcpuRatio": ocpu_to_vcpu_ratio,
        "partNumbers": part_numbers or [],
        "sourceNotes": source_notes or [],
    }


def build_payload() -> dict:
    xls_note = (
        "Pricing part numbers and metering are anchored to the Oracle localizable/global price-list extracts in "
        "pricing/data/xls-extract and pricing/data/price-list-extract."
    )
    shape_doc_note = (
        "Shape names and fixed/flex sizing behavior follow OCI Compute shape semantics as exposed by OCI Calculator "
        "and Oracle Compute shape documentation."
    )
    return {
        "metadata": {
            "generatedBy": "pricing/tools/build_vm_shape_rules.py",
            "description": "Declarative OCI VM shape registry for calculator-style VM quoting.",
        },
        "shapes": [
            shape("VM.Standard3.Flex", "flex", "intel", "standard", "X9", ocpu_to_vcpu_ratio=2, part_numbers=["B94176", "B94177"], source_notes=[xls_note, shape_doc_note]),
            shape("VM.Optimized3.Flex", "flex", "intel", "optimized", "X9", ocpu_to_vcpu_ratio=2, part_numbers=["B93311", "B93312"], source_notes=[xls_note, shape_doc_note]),
            shape("VM.Standard2.1", "fixed", "intel", "standard", "X7", product_label="Compute - Virtual Machine Standard - X7", fixed_ocpus=1, fixed_memory_gb=15, ocpu_to_vcpu_ratio=2, part_numbers=["B88514"], source_notes=[xls_note, shape_doc_note]),
            shape("VM.Standard2.2", "fixed", "intel", "standard", "X7", product_label="Compute - Virtual Machine Standard - X7", fixed_ocpus=2, fixed_memory_gb=30, ocpu_to_vcpu_ratio=2, part_numbers=["B88514"], source_notes=[xls_note, shape_doc_note]),
            shape("VM.Standard2.4", "fixed", "intel", "standard", "X7", product_label="Compute - Virtual Machine Standard - X7", fixed_ocpus=4, fixed_memory_gb=60, ocpu_to_vcpu_ratio=2, part_numbers=["B88514"], source_notes=[xls_note, shape_doc_note]),
            shape("VM.Standard2.8", "fixed", "intel", "standard", "X7", product_label="Compute - Virtual Machine Standard - X7", fixed_ocpus=8, fixed_memory_gb=120, ocpu_to_vcpu_ratio=2, part_numbers=["B88514"], source_notes=[xls_note, shape_doc_note]),
            shape("VM.Standard2.16", "fixed", "intel", "standard", "X7", product_label="Compute - Virtual Machine Standard - X7", fixed_ocpus=16, fixed_memory_gb=240, ocpu_to_vcpu_ratio=2, part_numbers=["B88514"], source_notes=[xls_note, shape_doc_note]),
            shape("VM.Standard2.24", "fixed", "intel", "standard", "X7", product_label="Compute - Virtual Machine Standard - X7", fixed_ocpus=24, fixed_memory_gb=320, ocpu_to_vcpu_ratio=2, part_numbers=["B88514"], source_notes=[xls_note, shape_doc_note]),
            shape("VM.Standard.E3.Flex", "flex", "amd", "standard", "E3", ocpu_to_vcpu_ratio=2, part_numbers=["B92306", "B92307"], source_notes=[xls_note]),
            shape("VM.Standard.E4.Flex", "flex", "amd", "standard", "E4", ocpu_to_vcpu_ratio=2, part_numbers=["B93113", "B93114"], source_notes=[xls_note]),
            shape("VM.Standard.E5.Flex", "flex", "amd", "standard", "E5", ocpu_to_vcpu_ratio=2, part_numbers=["B97384", "B97385"], source_notes=[xls_note]),
            shape("VM.Standard.E6.Flex", "flex", "amd", "standard", "E6", ocpu_to_vcpu_ratio=2, part_numbers=["B111129", "B111130"], source_notes=[xls_note]),
            shape("VM.DenseIO.E4.Flex", "flex", "amd", "denseio", "E4", ocpu_to_vcpu_ratio=2, part_numbers=["B93121", "B93122", "B93123"], source_notes=[xls_note]),
            shape("VM.DenseIO.E5.Flex", "flex", "amd", "denseio", "E5", ocpu_to_vcpu_ratio=2, part_numbers=["B98202", "B98203", "B98204"], source_notes=[xls_note]),
            shape("VM.Standard.A1.Flex", "flex", "ampere", "standard", "A1", ocpu_to_vcpu_ratio=1, part_numbers=["B93297", "B93298"], source_notes=[xls_note, shape_doc_note]),
            shape("VM.Standard.A2.Flex", "flex", "ampere", "standard", "A2", ocpu_to_vcpu_ratio=1, part_numbers=["B109529", "B109530"], source_notes=[xls_note, shape_doc_note]),
            shape("VM.Standard.A4.Flex", "flex", "ampere", "standard", "A4", ocpu_to_vcpu_ratio=1, part_numbers=["B112145", "B112146"], source_notes=[xls_note, shape_doc_note]),
            shape("BM.Standard.B1.44", "fixed", "intel", "standard", "B1", product_label="Compute - Bare Metal Standard - B1", fixed_ocpus=44, ocpu_to_vcpu_ratio=2, part_numbers=["B91119"], source_notes=[xls_note, shape_doc_note]),
            shape("BM.Standard2.52", "fixed", "intel", "standard", "X7", product_label="Compute - Bare Metal Standard - X7", fixed_ocpus=52, ocpu_to_vcpu_ratio=2, part_numbers=["B88513", "B89137"], source_notes=[xls_note, shape_doc_note]),
            shape("BM.DenseIO2.52", "fixed", "intel", "denseio", "X7", product_label="Compute - Bare Metal Dense I/O - X7", fixed_ocpus=52, ocpu_to_vcpu_ratio=2, part_numbers=["B88515", "B89139"], source_notes=[xls_note, shape_doc_note]),
            shape("BM.Standard1.36", "fixed", "intel", "standard", "X5", product_label="Compute - Bare Metal Standard - X5", fixed_ocpus=36, fixed_memory_gb=256, ocpu_to_vcpu_ratio=2, part_numbers=["B88315", "B86076"], source_notes=[xls_note, shape_doc_note]),
            shape("BM.DenseIO1.36", "fixed", "intel", "denseio", "X5", product_label="Compute - Bare Metal Dense I/O - X5", fixed_ocpus=36, fixed_memory_gb=512, ocpu_to_vcpu_ratio=2, part_numbers=["B86078"], source_notes=[xls_note, shape_doc_note]),
        ],
    }


def main() -> None:
    payload = build_payload()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
