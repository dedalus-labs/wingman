"""Usage analytics and token tracking."""

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

USAGE_FILE = Path.home() / ".wingman" / "usage.jsonl"


@dataclass
class UsageEvent:
    ts: float
    model: str
    prompt_tokens: int
    completion_tokens: int
    session_id: str | None = None


def log_usage(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    session_id: str | None = None,
) -> None:
    """Append usage event to log file."""
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)

    event = UsageEvent(
        ts=time.time(),
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        session_id=session_id,
    )

    with open(USAGE_FILE, "a") as f:
        f.write(json.dumps(asdict(event)) + "\n")


def _load_events(since: float | None = None, session_id: str | None = None) -> list[UsageEvent]:
    """Load events from log file, optionally filtered by timestamp and session."""
    if not USAGE_FILE.exists():
        return []

    events = []
    with open(USAGE_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if since and data.get("ts", 0) < since:
                    continue
                if session_id and data.get("session_id") != session_id:
                    continue
                events.append(UsageEvent(**data))
            except (json.JSONDecodeError, TypeError):
                continue
    return events


@dataclass
class UsageStats:
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    by_model: dict[str, dict]
    event_count: int


def get_stats(since: float | None = None, session_id: str | None = None) -> UsageStats:
    """Compute usage statistics from logged events."""
    events = _load_events(since, session_id)

    total_prompt = 0
    total_completion = 0
    by_model: dict[str, dict] = {}

    for e in events:
        total_prompt += e.prompt_tokens
        total_completion += e.completion_tokens

        if e.model not in by_model:
            by_model[e.model] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "calls": 0,
            }
        by_model[e.model]["prompt_tokens"] += e.prompt_tokens
        by_model[e.model]["completion_tokens"] += e.completion_tokens
        by_model[e.model]["calls"] += 1

    return UsageStats(
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        total_tokens=total_prompt + total_completion,
        by_model=by_model,
        event_count=len(events),
    )


def get_period_stats(session_id: str | None = None) -> dict[str, UsageStats]:
    """Get stats for today, this week, this month, and all-time."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    return {
        "today": get_stats(since=today.timestamp(), session_id=session_id),
        "week": get_stats(since=week_ago.timestamp(), session_id=session_id),
        "month": get_stats(since=month_start.timestamp(), session_id=session_id),
        "all_time": get_stats(since=None, session_id=session_id),
    }


def format_stats_display(session_id: str | None = None) -> str:
    """Format stats for display in /stats command."""
    periods = get_period_stats(session_id)

    def fmt_tokens(t: int) -> str:
        if t >= 1_000_000:
            return f"{t/1_000_000:.1f}M"
        if t >= 1_000:
            return f"{t/1_000:.1f}K"
        return str(t)

    if session_id:
        lines = [f"[bold #7aa2f7]Session Usage[/] ({session_id[:16]}...)\n"]
    else:
        lines = ["[bold #7aa2f7]Usage Analytics[/]\n"]

    lines.append("[bold]Period       Tokens     Calls[/]")
    for name, label in [("today", "Today"), ("week", "This Week"), ("month", "This Month"), ("all_time", "All Time")]:
        s = periods[name]
        lines.append(f"  {label:<10} {fmt_tokens(s.total_tokens):>8}  {s.event_count:>6}")

    all_time = periods["all_time"]
    if all_time.by_model:
        lines.append("\n[bold]By Model[/]")
        sorted_models = sorted(all_time.by_model.items(), key=lambda x: x[1]["calls"], reverse=True)
        for model, data in sorted_models[:10]:
            model_short = model.split("/")[-1]
            total = data["prompt_tokens"] + data["completion_tokens"]
            lines.append(f"  {model_short:<28} {fmt_tokens(total):>8}  {data['calls']:>4} calls")

    return "\n".join(lines)


def clear_usage() -> int:
    """Clear all usage data. Returns number of events deleted."""
    if not USAGE_FILE.exists():
        return 0
    count = len(_load_events())
    USAGE_FILE.unlink()
    return count


def rename_session_usage(old_id: str, new_id: str) -> int:
    """Update session_id in usage events when a session is renamed."""
    if not USAGE_FILE.exists():
        return 0

    updated = 0
    lines = []
    with open(USAGE_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("session_id") == old_id:
                    data["session_id"] = new_id
                    updated += 1
                lines.append(json.dumps(data))
            except json.JSONDecodeError:
                lines.append(line)

    if updated > 0:
        with open(USAGE_FILE, "w") as f:
            f.write("\n".join(lines) + "\n")

    return updated
