#!/usr/bin/env python3
"""Simple query benchmark for regression checks."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCENARIO_TAGS: dict[str, list[str]] = {
    "news_list": ["domain:news", "endpoint:/api/news", "operation:list"],
    "minutes_list": ["domain:minutes", "endpoint:/api/minutes", "operation:list"],
    "segments_list": ["domain:segments", "endpoint:/api/segments", "operation:list"],
}

BENCHMARK_PROFILES: dict[str, dict[str, dict[str, float]]] = {
    "dev": {
        "news_list": {"avg_ms": 350.0, "p95_ms": 550.0},
        "minutes_list": {"avg_ms": 350.0, "p95_ms": 550.0},
        "segments_list": {"avg_ms": 450.0, "p95_ms": 700.0},
    },
    "staging": {
        "news_list": {"avg_ms": 250.0, "p95_ms": 400.0},
        "minutes_list": {"avg_ms": 250.0, "p95_ms": 400.0},
        "segments_list": {"avg_ms": 250.0, "p95_ms": 400.0},
    },
    "prod": {
        "news_list": {"avg_ms": 180.0, "p95_ms": 300.0},
        "minutes_list": {"avg_ms": 200.0, "p95_ms": 320.0},
        "segments_list": {"avg_ms": 220.0, "p95_ms": 350.0},
    },
}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * p))))
    return float(ordered[k])


def _load_app_dependencies() -> dict[str, Any]:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from app.config import Config
    from app.database import init_db
    from app.repositories.minutes_repository import list_minutes as list_minutes_fn, upsert_minutes as upsert_minutes_fn
    from app.repositories.news_repository import list_articles as list_articles_fn, upsert_articles as upsert_articles_fn
    from app.repositories.segments_repository import (
        insert_segments as insert_segments_fn,
        list_segments as list_segments_fn,
    )

    return {
        "init_db": init_db,
        "Config": Config,
        "list_articles": list_articles_fn,
        "upsert_articles": upsert_articles_fn,
        "list_minutes": list_minutes_fn,
        "upsert_minutes": upsert_minutes_fn,
        "list_segments": list_segments_fn,
        "insert_segments": insert_segments_fn,
    }


def _seed_data(
    *,
    connection_provider: Callable[[], Any],
    upsert_articles_fn: Callable[..., tuple[int, int]],
    upsert_minutes_fn: Callable[..., tuple[int, int]],
    insert_segments_fn: Callable[..., int],
    rows: int = 300,
) -> None:
    with connection_provider() as conn:
        conn.execute(
            text(
                """
                TRUNCATE TABLE
                  news_articles,
                  council_minutes,
                  council_speech_segments
                RESTART IDENTITY
                """
            )
        )

    news_items = []
    minutes_items = []
    segment_items = []
    for i in range(rows):
        day = (i % 28) + 1
        news_items.append(
            {
                "source": "bench-source",
                "title": f"budget news {i}",
                "url": f"https://example.com/bench/news/{i}",
                "published_at": f"2026-02-{day:02d}T10:00:00Z",
                "summary": "budget update",
                "content": "budget agenda report",
                "keywords": ["budget", "agenda"],
            }
        )
        minutes_items.append(
            {
                "council": "seoul",
                "committee": "budget",
                "session": "301",
                "meeting_no": i % 10 + 1,
                "meeting_no_combined": f"301 {i % 10 + 1}th",
                "url": f"https://example.com/bench/minutes/{i}",
                "meeting_date": date(2026, 2, day),
                "content": "agenda and budget minutes",
                "tag": ["budget"],
                "attendee": {"count": 10},
                "agenda": ["agenda-item"],
            }
        )
        segment_items.append(
            {
                "council": "seoul",
                "committee": "budget",
                "session": "301",
                "meeting_no": i % 10 + 1,
                "meeting_no_combined": f"301 {i % 10 + 1}th",
                "meeting_date": date(2026, 2, day),
                "content": "segment budget text",
                "summary": "segment summary",
                "subject": "budget subject",
                "tag": ["budget"],
                "importance": (i % 3) + 1,
                "questioner": {"name": "member"},
                "answerer": [{"name": "official"}],
                "party": "party-a",
                "constituency": "district-1",
                "department": "finance",
            }
        )

    upsert_articles_fn(news_items, connection_provider=connection_provider)
    upsert_minutes_fn(minutes_items, connection_provider=connection_provider)
    insert_segments_fn(segment_items, connection_provider=connection_provider)


def _measure(name: str, fn, runs: int = 25) -> dict[str, float | list[str] | int]:
    durations = []
    for _ in range(runs):
        started = time.perf_counter()
        fn()
        durations.append((time.perf_counter() - started) * 1000.0)

    return {
        "name": name,
        "runs": int(runs),
        "tags": list(SCENARIO_TAGS.get(name, [])),
        "avg_ms": round(statistics.fmean(durations), 2),
        "p95_ms": round(percentile(durations, 0.95), 2),
        "min_ms": round(min(durations), 2),
        "max_ms": round(max(durations), 2),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark regression checks for primary list queries.")
    parser.add_argument(
        "--profile",
        choices=["none", "dev", "staging", "prod"],
        default=(os.getenv("BENCH_PROFILE", "none").strip().lower() or "none"),
        help="Threshold profile to enforce.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=max(1, int(os.getenv("BENCH_RUNS", "25"))),
        help="Per-scenario benchmark runs.",
    )
    parser.add_argument(
        "--seed-rows",
        type=int,
        default=max(50, int(os.getenv("BENCH_SEED_ROWS", "300"))),
        help="Rows to seed before running scenarios.",
    )
    return parser.parse_args()


def get_profile_thresholds(profile: str) -> dict[str, dict[str, float]] | None:
    normalized = (profile or "").strip().lower()
    if normalized in {"", "none"}:
        return None
    return BENCHMARK_PROFILES.get(normalized)


def evaluate_thresholds(
    results: dict[str, dict[str, float | list[str] | int]],
    *,
    profile: str,
    avg_threshold: float | None,
    p95_threshold: float | None,
) -> list[str]:
    failures: list[str] = []
    profile_thresholds = get_profile_thresholds(profile)

    if profile_thresholds is not None:
        for scenario_name, limits in profile_thresholds.items():
            stats = results.get(scenario_name)
            if stats is None:
                failures.append(f"{scenario_name}: missing benchmark result for profile {profile}")
                continue
            avg_ms = float(stats["avg_ms"])
            p95_ms = float(stats["p95_ms"])
            limit_avg = float(limits["avg_ms"])
            limit_p95 = float(limits["p95_ms"])
            if avg_ms > limit_avg:
                failures.append(
                    f"{scenario_name}: avg_ms {avg_ms:.2f} exceeded profile[{profile}] limit {limit_avg:.2f}"
                )
            if p95_ms > limit_p95:
                failures.append(
                    f"{scenario_name}: p95_ms {p95_ms:.2f} exceeded profile[{profile}] limit {limit_p95:.2f}"
                )
    elif profile not in {"", "none"}:
        failures.append(f"Unknown benchmark profile: {profile}")

    if avg_threshold is not None:
        for scenario_name, stats in results.items():
            avg_ms = float(stats["avg_ms"])
            if avg_ms > avg_threshold:
                failures.append(
                    f"{scenario_name}: avg_ms {avg_ms:.2f} exceeded global limit {avg_threshold:.2f}"
                )

    if p95_threshold is not None:
        for scenario_name, stats in results.items():
            p95_ms = float(stats["p95_ms"])
            if p95_ms > p95_threshold:
                failures.append(
                    f"{scenario_name}: p95_ms {p95_ms:.2f} exceeded global limit {p95_threshold:.2f}"
                )

    return failures


def _collect_results(
    *,
    list_articles_fn,
    list_minutes_fn,
    list_segments_fn,
    connection_provider: Callable[[], Any],
    runs: int,
) -> dict[str, dict[str, float | list[str] | int]]:
    return {
        "news_list": _measure(
            "news_list",
            lambda: list_articles_fn(
                q="budget",
                source="bench-source",
                date_from="2026-02-01",
                date_to="2026-02-28",
                page=1,
                size=20,
                connection_provider=connection_provider,
            ),
            runs=runs,
        ),
        "minutes_list": _measure(
            "minutes_list",
            lambda: list_minutes_fn(
                q="agenda",
                council="seoul",
                committee="budget",
                session="301",
                meeting_no=None,
                date_from="2026-02-01",
                date_to="2026-02-28",
                page=1,
                size=20,
                connection_provider=connection_provider,
            ),
            runs=runs,
        ),
        "segments_list": _measure(
            "segments_list",
            lambda: list_segments_fn(
                q="segment",
                council="seoul",
                committee="budget",
                session="301",
                meeting_no=None,
                importance=2,
                party="party-a",
                constituency="district-1",
                department="finance",
                date_from="2026-02-01",
                date_to="2026-02-28",
                page=1,
                size=20,
                connection_provider=connection_provider,
            ),
            runs=runs,
        ),
    }


def main() -> int:
    args = _parse_args()
    dependencies = _load_app_dependencies()

    config_class = dependencies["Config"]
    init_db_fn = dependencies["init_db"]

    config = config_class()
    db_engine = init_db_fn(config.database_url)
    connection_provider = db_engine.begin
    _seed_data(
        connection_provider=connection_provider,
        upsert_articles_fn=dependencies["upsert_articles"],
        upsert_minutes_fn=dependencies["upsert_minutes"],
        insert_segments_fn=dependencies["insert_segments"],
        rows=max(50, int(args.seed_rows)),
    )
    results = _collect_results(
        list_articles_fn=dependencies["list_articles"],
        list_minutes_fn=dependencies["list_minutes"],
        list_segments_fn=dependencies["list_segments"],
        connection_provider=connection_provider,
        runs=max(1, int(args.runs)),
    )

    avg_threshold = None
    p95_threshold = None
    avg_threshold_raw = os.getenv("BENCH_FAIL_THRESHOLD_MS")
    p95_threshold_raw = os.getenv("BENCH_FAIL_P95_THRESHOLD_MS")
    if avg_threshold_raw:
        avg_threshold = float(avg_threshold_raw)
    if p95_threshold_raw:
        p95_threshold = float(p95_threshold_raw)

    output: dict[str, Any] = dict(results)
    output["_meta"] = {
        "profile": args.profile,
        "profile_thresholds": get_profile_thresholds(args.profile),
        "global_thresholds": {"avg_ms": avg_threshold, "p95_ms": p95_threshold},
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    failures = evaluate_thresholds(
        results,
        profile=args.profile,
        avg_threshold=avg_threshold,
        p95_threshold=p95_threshold,
    )
    if failures:
        print("Benchmark regression check failed.", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
