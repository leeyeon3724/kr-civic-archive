#!/usr/bin/env python3
"""Compare split-count vs window total strategies for list endpoints."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DOMAIN_QUERIES: dict[str, dict[str, str]] = {
    "news": {
        "list": """
            SELECT id
            FROM news_articles
            ORDER BY published_at DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
        """,
        "count": "SELECT COUNT(*) AS total FROM news_articles",
        "window": """
            SELECT id, total
            FROM (
                SELECT id, published_at, COUNT(*) OVER() AS total
                FROM news_articles
            ) q
            ORDER BY published_at DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
        """,
    },
    "minutes": {
        "list": """
            SELECT id
            FROM council_minutes
            ORDER BY meeting_date DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
        """,
        "count": "SELECT COUNT(*) AS total FROM council_minutes",
        "window": """
            SELECT id, total
            FROM (
                SELECT id, meeting_date, COUNT(*) OVER() AS total
                FROM council_minutes
            ) q
            ORDER BY meeting_date DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
        """,
    },
    "segments": {
        "list": """
            SELECT id
            FROM council_speech_segments
            ORDER BY meeting_date DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
        """,
        "count": "SELECT COUNT(*) AS total FROM council_speech_segments",
        "window": """
            SELECT id, total
            FROM (
                SELECT id, meeting_date, COUNT(*) OVER() AS total
                FROM council_speech_segments
            ) q
            ORDER BY meeting_date DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
        """,
    },
}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * p))))
    return float(ordered[index])


def summarize_timings(values: list[float]) -> dict[str, float]:
    return {
        "avg_ms": round(statistics.fmean(values), 2) if values else 0.0,
        "p95_ms": round(percentile(values, 0.95), 2),
        "min_ms": round(min(values), 2) if values else 0.0,
        "max_ms": round(max(values), 2) if values else 0.0,
    }


def compare_strategy_timings(
    conn: Any,
    *,
    list_sql: str,
    count_sql: str,
    window_sql: str,
    runs: int,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    split_roundtrip_ms: list[float] = []
    split_list_ms: list[float] = []
    split_count_ms: list[float] = []
    window_roundtrip_ms: list[float] = []

    for _ in range(max(1, int(runs))):
        list_started = time.perf_counter()
        conn.execute(text(list_sql), {"limit": limit, "offset": offset}).mappings().all()
        list_elapsed = (time.perf_counter() - list_started) * 1000.0

        count_started = time.perf_counter()
        conn.execute(text(count_sql)).scalar() or 0
        count_elapsed = (time.perf_counter() - count_started) * 1000.0

        split_roundtrip_ms.append(list_elapsed + count_elapsed)
        split_list_ms.append(list_elapsed)
        split_count_ms.append(count_elapsed)

        window_started = time.perf_counter()
        conn.execute(text(window_sql), {"limit": limit, "offset": offset}).mappings().all()
        window_elapsed = (time.perf_counter() - window_started) * 1000.0
        window_roundtrip_ms.append(window_elapsed)

    return {
        "split_strategy_ms": {
            "roundtrip": summarize_timings(split_roundtrip_ms),
            "list_query": summarize_timings(split_list_ms),
            "count_query": summarize_timings(split_count_ms),
        },
        "window_strategy_ms": {
            "roundtrip": summarize_timings(window_roundtrip_ms),
        },
        "notes": {
            "window_total_absent_when_no_rows": True,
            "split_total_always_available": True,
            "page_limit": int(limit),
            "page_offset": int(offset),
            "runs": int(runs),
        },
    }


def _load_runtime() -> tuple[Any, Any]:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from app.config import Config
    from app.database import init_db

    config = Config()
    engine = init_db(config.database_engine_url)
    return config, engine


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare list total-count query strategies.")
    parser.add_argument("--runs", type=int, default=30, help="Per-domain benchmark runs.")
    parser.add_argument("--limit", type=int, default=20, help="Pagination limit.")
    parser.add_argument("--offset", type=int, default=0, help="Pagination offset.")
    parser.add_argument("--output-json", default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    _config, engine = _load_runtime()

    report: dict[str, Any] = {
        "_meta": {
            "runs": int(args.runs),
            "limit": int(args.limit),
            "offset": int(args.offset),
        }
    }

    with engine.begin() as conn:
        for domain, queries in DOMAIN_QUERIES.items():
            report[domain] = compare_strategy_timings(
                conn,
                list_sql=queries["list"],
                count_sql=queries["count"],
                window_sql=queries["window"],
                runs=int(args.runs),
                limit=int(args.limit),
                offset=int(args.offset),
            )

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.output_json:
        output_path = Path(args.output_json).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
