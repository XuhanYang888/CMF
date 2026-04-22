#!/usr/bin/env python3

from __future__ import annotations
import json
import sqlite3
import sys
from pathlib import Path

def export_awards(db_path: Path, output_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT p.id AS person_id,
                   p.name,
                   a.year,
                   a.group_name,
                   a.score_range,
                   a.grade,
                   a.source_csv
            FROM people p
            JOIN awards a ON a.person_id = p.id
            ORDER BY p.name, a.year, a.group_name, a.score_range
            """
        ).fetchall()

    people: list[dict] = []
    current: dict | None = None

    for row in rows:
        if current is None or current["name"] != row["name"]:
            if current is not None:
                people.append(current)
            current = {
                "id": row["person_id"],
                "name": row["name"],
                "awards": [],
            }

        current["awards"].append(
            {
                "year": row["year"],
                "group_name": row["group_name"],
                "score_range": row["score_range"],
                "grade": row["grade"],
                "source_csv": Path(row["source_csv"]).name,
            }
        )

    if current is not None:
        people.append(current)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump({"people": people}, f, ensure_ascii=False, indent=2)

def main(argv: list[str]) -> int:
    db_path = Path(argv[0]) if argv else Path("contest_data/awards.sqlite3")
    output_path = Path(argv[1]) if len(argv) > 1 else Path("docs/awards.json")

    export_awards(db_path, output_path)
    print(f"Wrote {output_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))