#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REQ_007_SCHEMA_VERSION = "req-007.ground-graph-snapshot-ingestion.v1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _print_human(message: str) -> None:
    print(f"[{_utc_now_iso()}] {message}")


def _require_nonempty_str(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _checksum_sha256(payload: Mapping[str, Any]) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _anchor_id(anchor: Mapping[str, str]) -> str:
    return "::".join(
        [
            anchor["project_id"],
            anchor["era_id"],
            anchor["plan_id"],
            anchor["phase_id"],
            anchor["run_id"],
            anchor["linked_project_id"],
            anchor["relationship"],
        ]
    )


def load_ground_graph_snapshot(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("ground_graph_snapshot must be a JSON object")
    return payload


def ingest_ground_graph_snapshot(
    snapshot: Mapping[str, Any],
    *,
    source_path: str | None = None,
    ingested_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise ValueError("ground_graph_snapshot must be an object")
    schema_version = _require_nonempty_str(snapshot.get("schema_version"), label="ground_graph_snapshot.schema_version")
    captured_at = _require_nonempty_str(snapshot.get("captured_at"), label="ground_graph_snapshot.captured_at")
    graph_id = _require_nonempty_str(snapshot.get("graph_id"), label="ground_graph_snapshot.graph_id")
    raw_links = snapshot.get("lineage_links")
    if not isinstance(raw_links, list) or not raw_links:
        raise ValueError("ground_graph_snapshot.lineage_links must be a non-empty list")

    anchors: list[dict[str, str]] = []
    seen_anchor_ids: set[str] = set()
    for idx, row in enumerate(raw_links):
        if not isinstance(row, Mapping):
            raise ValueError(f"ground_graph_snapshot.lineage_links[{idx}] must be an object")
        anchor = {
            "project_id": _require_nonempty_str(
                row.get("project_id"), label=f"ground_graph_snapshot.lineage_links[{idx}].project_id"
            ),
            "era_id": _require_nonempty_str(row.get("era_id"), label=f"ground_graph_snapshot.lineage_links[{idx}].era_id"),
            "plan_id": _require_nonempty_str(
                row.get("plan_id"), label=f"ground_graph_snapshot.lineage_links[{idx}].plan_id"
            ),
            "phase_id": _require_nonempty_str(
                row.get("phase_id"), label=f"ground_graph_snapshot.lineage_links[{idx}].phase_id"
            ),
            "run_id": _require_nonempty_str(row.get("run_id"), label=f"ground_graph_snapshot.lineage_links[{idx}].run_id"),
            "linked_project_id": _require_nonempty_str(
                row.get("linked_project_id"), label=f"ground_graph_snapshot.lineage_links[{idx}].linked_project_id"
            ),
            "relationship": _require_nonempty_str(
                row.get("relationship"), label=f"ground_graph_snapshot.lineage_links[{idx}].relationship"
            ),
        }
        anchor["anchor_id"] = _anchor_id(anchor)
        if anchor["anchor_id"] in seen_anchor_ids:
            continue
        seen_anchor_ids.add(anchor["anchor_id"])
        anchors.append(anchor)

    anchors.sort(key=lambda item: item["anchor_id"])
    ingested_at_value = _require_nonempty_str(ingested_at or _utc_now_iso(), label="ingested_at")
    output = {
        "requirement_id": "REQ-007",
        "surface": "ground_graph_snapshot_ingestion",
        "schema_version": REQ_007_SCHEMA_VERSION,
        "ingested_at": ingested_at_value,
        "source_artifact": {
            "path": source_path or "<inline>",
            "schema_version": schema_version,
            "captured_at": captured_at,
            "graph_id": graph_id,
            "checksum_sha256": _checksum_sha256(snapshot),
        },
        "lineage_anchors": anchors,
        "lineage_index": {
            "project_ids": sorted({item["project_id"] for item in anchors}),
            "era_ids": sorted({item["era_id"] for item in anchors}),
            "plan_ids": sorted({item["plan_id"] for item in anchors}),
            "phase_ids": sorted({item["phase_id"] for item in anchors}),
            "run_ids": sorted({item["run_id"] for item in anchors}),
            "linked_project_ids": sorted({item["linked_project_id"] for item in anchors}),
        },
    }
    return output


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="REQ-007 Ground graph snapshot ingestion")
    parser.add_argument("--input", required=True, help="Path to Ground graph snapshot JSON")
    parser.add_argument("--output", help="Path to write canonical ingestion JSON")
    parser.add_argument("--source-path", help="Source path string stored in output")
    parser.add_argument("--ingested-at", help="ISO-8601 timestamp to stamp in output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser().resolve()
    source_path = args.source_path or str(input_path)
    _print_human(f"Loading Ground graph snapshot from {input_path}")
    snapshot = load_ground_graph_snapshot(input_path)

    _print_human("Ingesting snapshot into canonical REQ-007 lineage context")
    ingested = ingest_ground_graph_snapshot(snapshot, source_path=source_path, ingested_at=args.ingested_at)

    rendered = json.dumps(ingested, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        _print_human(
            f"Wrote ingestion artifact to {output_path} with {len(ingested['lineage_anchors'])} lineage anchor rows"
        )
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
