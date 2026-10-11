"""Optional operator-selected planning limits; no default changes for existing CLI users."""

from __future__ import annotations

from typing import Any


def parse_max_plan_tasks(value: Any) -> int | None:
    """Accept an explicit integer limit from JSON or CLI, rejecting lossy coercion."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("max_plan_tasks must be an integer between 1 and 400")
    try:
        parsed = int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("max_plan_tasks must be an integer between 1 and 400") from exc
    if not 1 <= parsed <= 400:
        raise ValueError("max_plan_tasks must be an integer between 1 and 400")
    return parsed


def plan_task_limit_errors(tasks: Any, maximum: int | None) -> list[dict[str, Any]]:
    """Bound the generated plan without removing tasks or weakening coverage checks."""
    if maximum is None or not isinstance(tasks, list) or len(tasks) <= maximum:
        return []
    return [{
        "code": "planner_task_limit_exceeded",
        "message": f"Plan has {len(tasks)} tasks; the operator-selected maximum is {maximum}. Replan within the limit; no tasks were truncated.",
        "task_count": len(tasks),
        "max_plan_tasks": maximum,
    }]
