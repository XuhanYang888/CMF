#!/usr/bin/env python3

"""Build a SQLite database from contest CSV exports.

The database groups awards by person name only. School and location are ignored,
so rows with the same first/last name are stored under the same person record.

Usage:
    python build_awards_db.py [csv_path1] [csv_path2] ... [output_db]

If a path is a directory, all CSV files under that directory are loaded.
If a path is a file, that single CSV file is loaded.
If the final argument ends with .db, .sqlite, or .sqlite3, it is used as the
output database path.

Defaults:
    all contest csv directories under contest_data/
    output_db: contest_data/awards.sqlite3
"""

from __future__ import annotations

import csv
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


YEAR_RE = re.compile(r"(\d{4})")


@dataclass(frozen=True)
class AwardRow:
    name: str
    year: int
    group_name: str
    score_range: str
    grade: str
    source_csv: str


def normalize_name(name: str) -> str:
    return " ".join(name.split())


def parse_year_from_filename(csv_path: Path) -> int:
    match = YEAR_RE.search(csv_path.stem)
    if match:
        return int(match.group(1))
    raise ValueError(f"Could not determine year from filename: {csv_path.name}")


def collect_csv_files(paths: list[Path]) -> list[Path]:
    csv_files: list[Path] = []
    for path in paths:
        if path.is_file():
            if path.suffix.lower() != ".csv":
                raise ValueError(f"Expected a CSV file: {path}")
            csv_files.append(path)
        elif path.is_dir():
            csv_files.extend(sorted(path.rglob("*.csv")))
        else:
            raise FileNotFoundError(f"CSV path not found: {path}")
    return sorted(csv_files)


def collect_awards(csv_paths: list[Path]) -> list[AwardRow]:
    awards: list[AwardRow] = []

    for csv_path in csv_paths:
        year = parse_year_from_filename(csv_path)
        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = normalize_name(row.get("name", ""))
                if not name:
                    continue
                awards.append(
                    AwardRow(
                        name=name,
                        year=year,
                        group_name=row.get("group", "").strip(),
                        score_range=row.get("score_range", "").strip(),
                        grade=row.get("grade", "").strip(),
                        source_csv=str(csv_path),
                    )
                )

    return awards


def build_database(csv_paths: list[Path], output_db: Path) -> tuple[int, int]:
    awards = collect_awards(csv_paths)
    output_db.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(output_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            DROP TABLE IF EXISTS awards;
            DROP TABLE IF EXISTS people;

            CREATE TABLE people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE awards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                score_range TEXT NOT NULL,
                grade TEXT NOT NULL,
                source_csv TEXT NOT NULL,
                FOREIGN KEY (person_id) REFERENCES people(id)
            );

            CREATE INDEX idx_awards_person_id ON awards(person_id);
            CREATE INDEX idx_awards_year ON awards(year);
            """
        )

        person_ids: dict[str, int] = {}
        for award in awards:
            person_id = person_ids.get(award.name)
            if person_id is None:
                cur = conn.execute(
                    "INSERT INTO people (name) VALUES (?)", (award.name,)
                )
                person_id = int(cur.lastrowid)
                person_ids[award.name] = person_id

            conn.execute(
                """
                INSERT INTO awards (person_id, year, group_name, score_range, grade, source_csv)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    person_id,
                    award.year,
                    award.group_name,
                    award.score_range,
                    award.grade,
                    award.source_csv,
                ),
            )

        conn.commit()

    return len(person_ids), len(awards)


def parse_args(argv: list[str]) -> tuple[list[Path], Path]:
    if argv and argv[0].lower() in {"-h", "--help"}:
        raise SystemExit(
            "Usage: python build_awards_db.py [csv_path1] [csv_path2] ... [output_db]\n"
            "If output_db is omitted, awards.sqlite3 is used.\n"
            "CSV paths may be directories or individual CSV files."
        )

    output_db = Path("contest_data/awards.sqlite3")
    args = [Path(p) for p in argv]
    if args and args[-1].suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        output_db = args[-1]
        args = args[:-1]

    if not args:
        contest_root = Path("contest_data")
        if contest_root.is_dir():
            default_dirs = sorted(
                p / "csv"
                for p in contest_root.iterdir()
                if p.is_dir() and (p / "csv").is_dir()
            )
        else:
            default_dirs = sorted(
                p / "csv"
                for p in Path(".").iterdir()
                if p.is_dir() and (p / "csv").is_dir()
            )
        if default_dirs:
            args = default_dirs
        else:
            args = [Path("contest_data/Euclid/csv"), Path("contest_data/CSMC/csv"), Path("contest_data/CIMC/csv")]

    csv_files = collect_csv_files(args)
    if not csv_files:
        raise SystemExit("No CSV files found in the provided path(s).")
    return csv_files, output_db


def main() -> int:
    try:
        csv_paths, output_db = parse_args(sys.argv[1:])
    except SystemExit as exc:
        print(exc)
        return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    people_count, award_count = build_database(csv_paths, output_db)
    print(f"Wrote {award_count} awards for {people_count} people to {output_db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
