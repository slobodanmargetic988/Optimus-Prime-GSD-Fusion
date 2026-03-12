#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "docs" / "plans" / "BP_EPICS_CATALOG.json"
TECH_STACK_PATH = REPO_ROOT / "docs" / "plans" / "BP_MOBILE_TECH_STACK.md"


def _load_catalog(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid catalog format: {path}")
    return payload


def _render_epic(epic: dict[str, Any]) -> str:
    out = [f"{epic.get('epic_id', 'UNKNOWN')} - {epic.get('title', 'Untitled')}"]
    vision = epic.get("vision")
    if isinstance(vision, str) and vision.strip():
        out.append(f"Vision: {vision.strip()}")
    outcomes = epic.get("target_outcomes", [])
    if isinstance(outcomes, list) and outcomes:
        out.append("Outcomes:")
        out.extend([f"- {item}" for item in outcomes if isinstance(item, str)])
    deliverables = epic.get("deliverables", [])
    if isinstance(deliverables, list) and deliverables:
        out.append("Deliverables:")
        out.extend([f"- {item}" for item in deliverables if isinstance(item, str)])
    notes = epic.get("notes")
    if isinstance(notes, str) and notes.strip():
        out.append(f"Notes: {notes.strip()}")
    return "\n".join(out)


def cmd_list(args: argparse.Namespace) -> int:
    catalog = _load_catalog(Path(args.catalog))
    epics = catalog.get("epics", [])
    if not isinstance(epics, list):
        raise SystemExit("Catalog field 'epics' must be a list")
    for epic in epics:
        if not isinstance(epic, dict):
            continue
        print(f"{epic.get('epic_id', 'UNKNOWN')}: {epic.get('title', 'Untitled')}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    catalog = _load_catalog(Path(args.catalog))
    epics = catalog.get("epics", [])
    if not isinstance(epics, list):
        raise SystemExit("Catalog field 'epics' must be a list")
    wanted = args.epic_id.strip().upper()
    for epic in epics:
        if not isinstance(epic, dict):
            continue
        if str(epic.get("epic_id", "")).upper() == wanted:
            print(_render_epic(epic))
            return 0
    raise SystemExit(f"Epic not found: {wanted}")


def cmd_export(args: argparse.Namespace) -> int:
    catalog = _load_catalog(Path(args.catalog))
    epics = catalog.get("epics", [])
    if not isinstance(epics, list):
        raise SystemExit("Catalog field 'epics' must be a list")
    selected_ids = {value.strip().upper() for value in args.epic_id} if args.epic_id else set()
    picked = []
    for epic in epics:
        if not isinstance(epic, dict):
            continue
        eid = str(epic.get("epic_id", "")).upper()
        if selected_ids and eid not in selected_ids:
            continue
        picked.append(epic)

    payload = {
        "schema_version": "1.0",
        "program": catalog.get("program", "BP"),
        "selected_epics": picked,
        "tech_stack_file": str(TECH_STACK_PATH),
    }

    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(str(out_path))
    return 0


def cmd_mission_scope(args: argparse.Namespace) -> int:
    catalog = _load_catalog(Path(args.catalog))
    epics = catalog.get("epics", [])
    if not isinstance(epics, list):
        raise SystemExit("Catalog field 'epics' must be a list")

    selected_ids = {value.strip().upper() for value in args.epic_id}
    picked = []
    for epic in epics:
        if not isinstance(epic, dict):
            continue
        eid = str(epic.get("epic_id", "")).upper()
        if eid in selected_ids:
            picked.append(epic)
    if not picked:
        raise SystemExit("No matching epic IDs selected")

    mission_lines = [
        "# BP Mission Draft",
        "",
        "Build the next BP iteration focused on these selected epics:",
        "",
    ]
    scope_lines = [
        "# BP Scope Draft",
        "",
        "This scope is mobile-first. Follow stack policy in:",
        f"- {TECH_STACK_PATH}",
        "",
        "Selected epic boundaries and deliverables:",
        "",
    ]
    for epic in picked:
        mission_lines.append(f"- {epic.get('epic_id')}: {epic.get('title')}")
        scope_lines.append(_render_epic(epic))
        scope_lines.append("")

    mission_path = Path(args.mission_output).resolve()
    scope_path = Path(args.scope_output).resolve()
    mission_path.parent.mkdir(parents=True, exist_ok=True)
    scope_path.parent.mkdir(parents=True, exist_ok=True)
    mission_path.write_text("\n".join(mission_lines).rstrip() + "\n", encoding="utf-8")
    scope_path.write_text("\n".join(scope_lines).rstrip() + "\n", encoding="utf-8")
    print(f"mission_file={mission_path}")
    print(f"scope_file={scope_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="BP epics helper CLI (terminal-only, argument driven)."
    )
    parser.add_argument(
        "--catalog",
        default=str(CATALOG_PATH),
        help="Path to BP epic catalog JSON.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List all available epics.")
    list_parser.set_defaults(func=cmd_list)

    show_parser = sub.add_parser("show", help="Show one epic by ID.")
    show_parser.add_argument("--epic-id", required=True, help="Epic ID (example: BP-001).")
    show_parser.set_defaults(func=cmd_show)

    export_parser = sub.add_parser("export", help="Export selected epics to JSON.")
    export_parser.add_argument("--epic-id", action="append", help="Repeat to select more epic IDs.")
    export_parser.add_argument("--output", required=True, help="Output JSON path.")
    export_parser.set_defaults(func=cmd_export)

    ms_parser = sub.add_parser(
        "mission-scope",
        help="Generate mission/scope draft files from selected epic IDs.",
    )
    ms_parser.add_argument("--epic-id", action="append", required=True, help="Repeat for each epic ID.")
    ms_parser.add_argument("--mission-output", required=True, help="Mission markdown output path.")
    ms_parser.add_argument("--scope-output", required=True, help="Scope markdown output path.")
    ms_parser.set_defaults(func=cmd_mission_scope)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
