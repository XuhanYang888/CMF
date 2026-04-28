#!/usr/bin/env python3

"""Build a SQLite database from contest CSV exports and compute ratings.

Ratings use the formula from rating_planning.md:

    P = C * G * 0.9^t
    Score = sum(0.8^i * P_i) for the top 5 adjusted results

Contest base values:

    Euclid 100, CSMC 90, CIMC 70, Hypatia 60, Fermat 60,
    Galois 50, Cayley 50, Fryer 40, Pascal 40, Gauss 15

Group multipliers:

    1/I = 1.00, 2/II = 0.90, 3/III = 0.75, 4/IV = 0.60, 5/V = 0.45

The database groups awards by person name only. School and location are ignored,
so rows with the same first/last name are stored under the same person record.

Ratings are computed during the rebuild and stored in the ratings table.

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

import argparse
import csv
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_DB = Path("contest_data/awards.sqlite3")


YEAR_RE = re.compile(r"(\d{4})")

DEFAULT_CURRENT_SCHOOL_YEAR_END = 2026
MAX_RESULTS_PER_PERSON = 5
CONSISTENCY_DECAY = 0.8
YEAR_DECAY_FACTOR = 0.9

CONTEST_BASE_VALUES: dict[str, float] = {
    "Euclid": 100.0,
    "CSMC": 90.0,
    "CIMC": 70.0,
    "Hypatia": 60.0,
    "Fermat": 60.0,
    "Galois": 50.0,
    "Cayley": 50.0,
    "Fryer": 40.0,
    "Pascal": 40.0,
    "Gauss": 15.0,
}

GROUP_MULTIPLIERS: dict[str, float] = {
    "1": 1.0,
    "2": 0.9,
    "3": 0.75,
    "4": 0.6,
    "5": 0.45,
    "I": 1.0,
    "II": 0.9,
    "III": 0.75,
    "IV": 0.6,
    "V": 0.45,
}


@dataclass(frozen=True)
class AwardRow:
    name: str
    year: int
    group_name: str
    score_range: str
    grade: str
    source_csv: str


@dataclass(frozen=True)
class Award:
    year: int
    group_name: str
    source_csv: str


def normalize_name(name: str) -> str:
    return " ".join(name.split())


def parse_year_from_filename(csv_path: Path) -> int:
    match = YEAR_RE.search(csv_path.stem)
    if match:
        return int(match.group(1))
    raise ValueError(f"Could not determine year from filename: {csv_path.name}")


def extract_contest_name(source_csv: str) -> str:
    """Extract the contest token from a source CSV like 2025Euclid.csv."""
    filename = source_csv.replace("\\", "/").rsplit("/", 1)[-1]
    stem = Path(filename).stem

    match = re.match(r"^\d{4}(.*)$", stem)
    contest = match.group(1) if match else stem

    if contest.startswith("Gauss"):
        return "Gauss"

    return contest


def parse_group_multiplier(group_name: str) -> float:
    """Parse a group label into a multiplier, defaulting to Group 5."""
    text = (group_name or "").strip().upper()
    if not text:
        return GROUP_MULTIPLIERS["5"]

    if text in GROUP_MULTIPLIERS:
        return GROUP_MULTIPLIERS[text]

    digit_match = re.search(r"([1-5])", text)
    if digit_match:
        return GROUP_MULTIPLIERS[digit_match.group(1)]

    return GROUP_MULTIPLIERS["5"]


def school_year_end_for_award(award: Award) -> int:
    """Map contest year to school-year-end year for decay logic."""
    contest_name = extract_contest_name(award.source_csv)
    if contest_name in {"CIMC", "CSMC"}:
        return award.year + 1
    return award.year


def award_points(
    award: Award,
    *,
    current_school_year_end: int,
) -> float:
    contest_name = extract_contest_name(award.source_csv)
    contest_base = CONTEST_BASE_VALUES.get(contest_name, CONTEST_BASE_VALUES["Gauss"])
    group_multiplier = parse_group_multiplier(award.group_name)

    result_school_year_end = school_year_end_for_award(award)
    years_old = max(current_school_year_end - result_school_year_end, 0)
    return contest_base * group_multiplier * (YEAR_DECAY_FACTOR**years_old)


def rating_from_awards(
    awards: list[Award],
    *,
    current_school_year_end: int,
) -> tuple[float, int]:
    if not awards:
        return 0.0, 0

    adjusted = [
        award_points(
            award,
            current_school_year_end=current_school_year_end,
        )
        for award in awards
    ]
    adjusted.sort(reverse=True)

    top = adjusted[:MAX_RESULTS_PER_PERSON]
    weighted_sum = sum((CONSISTENCY_DECAY**i) * p for i, p in enumerate(top))

    return weighted_sum, len(adjusted)


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


def store_ratings(
    conn: sqlite3.Connection,
    *,
    current_school_year_end: int,
) -> int:
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT p.id AS person_id,
               p.name AS person_name,
               a.year,
               a.group_name,
               a.source_csv
        FROM people p
        LEFT JOIN awards a ON a.person_id = p.id
        ORDER BY p.id
        """
    ).fetchall()

    people: dict[int, tuple[str, list[Award]]] = {}
    for row in rows:
        person_id = int(row["person_id"])
        person_name = row["person_name"]
        if person_id not in people:
            people[person_id] = (person_name, [])

        if row["year"] is not None:
            people[person_id][1].append(
                Award(
                    year=int(row["year"]),
                    group_name=row["group_name"] or "",
                    source_csv=row["source_csv"] or "",
                )
            )

    conn.executescript(
        """
        DROP TABLE IF EXISTS ratings;

        CREATE TABLE ratings (
            person_id INTEGER PRIMARY KEY,
            rating REAL NOT NULL,
            results_used INTEGER NOT NULL,
            current_year INTEGER NOT NULL,
            formula TEXT NOT NULL,
            computed_at TEXT NOT NULL,
            FOREIGN KEY (person_id) REFERENCES people(id)
        );
        """
    )

    now = datetime.now(datetime.UTC).replace(microsecond=0).isoformat()

    rating_rows: list[tuple[int, float, int, int, str, str]] = []
    for person_id, (_name, awards) in people.items():
        rating, results_count = rating_from_awards(
            awards,
            current_school_year_end=current_school_year_end,
        )
        rating_rows.append(
            (
                person_id,
                round(rating, 4),
                min(results_count, MAX_RESULTS_PER_PERSON),
                current_school_year_end,
                "C*G*(0.9**t)",
                now,
            )
        )

    conn.executemany(
        """
        INSERT INTO ratings (
            person_id,
            rating,
            results_used,
            current_year,
            formula,
            computed_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rating_rows,
    )

    return len(rating_rows)


def build_ratings(
    db_path: Path,
    *,
    current_school_year_end: int,
) -> int:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        rating_count = store_ratings(
            conn,
            current_school_year_end=current_school_year_end,
        )
        conn.commit()

        print(
            f"Stored ratings for {rating_count} people "
            f"(school_year_end={current_school_year_end}, formula=C*G*(0.9**t))."
        )

        print("\nTop 25 ratings:")
        top_rows = conn.execute(
            """
            SELECT p.name, r.rating, r.results_used
            FROM ratings r
            JOIN people p ON p.id = r.person_id
            ORDER BY r.rating DESC, r.results_used DESC, p.name ASC
            LIMIT 25
            """
        ).fetchall()

        for i, row in enumerate(top_rows, start=1):
            print(
                f"{i:>2}. {row['name']:<35} {row['rating']:>6.2f}  (n={row['results_used']})"
            )

        return rating_count


def build_database(
    csv_paths: list[Path],
    output_db: Path,
    *,
    current_school_year_end: int = DEFAULT_CURRENT_SCHOOL_YEAR_END,
) -> tuple[int, int, int]:
    awards = collect_awards(csv_paths)
    output_db.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(output_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            DROP TABLE IF EXISTS ratings;
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

        ratings_count = store_ratings(
            conn,
            current_school_year_end=current_school_year_end,
        )

        conn.commit()

    return len(person_ids), len(awards), ratings_count


def parse_args(argv: list[str]) -> tuple[list[Path], Path]:
    if argv and argv[0].lower() in {"-h", "--help"}:
        raise SystemExit(
            "Usage: python build_awards_db.py [csv_path1] [csv_path2] ... [output_db]\n"
            "If output_db is omitted, awards.sqlite3 is used.\n"
            "CSV paths may be directories or individual CSV files."
        )

    output_db = DEFAULT_DB
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
            args = [
                Path("contest_data/Euclid/csv"),
                Path("contest_data/CSMC/csv"),
                Path("contest_data/CIMC/csv"),
            ]

    csv_files = collect_csv_files(args)
    if not csv_files:
        raise SystemExit("No CSV files found in the provided path(s).")
    return csv_files, output_db


def parse_ratings_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute ratings in an existing awards.sqlite3 database"
    )
    parser.add_argument(
        "db_path",
        nargs="?",
        default=str(DEFAULT_DB),
        help="Path to awards.sqlite3 (default: contest_data/awards.sqlite3)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_CURRENT_SCHOOL_YEAR_END,
        help="Current school-year-end year (e.g. 2026 for 2025/26)",
    )
    return parser.parse_args(argv)


def main() -> int:
    try:
        if "--ratings-only" in sys.argv[1:]:
            ratings_argv = [arg for arg in sys.argv[1:] if arg != "--ratings-only"]
            ratings_args = parse_ratings_args(ratings_argv)
            build_ratings(
                Path(ratings_args.db_path),
                current_school_year_end=ratings_args.year,
            )
            return 0

        csv_paths, output_db = parse_args(sys.argv[1:])
    except SystemExit as exc:
        print(exc)
        return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    people_count, award_count, rating_count = build_database(csv_paths, output_db)
    print(
        f"Wrote {award_count} awards and {rating_count} ratings for {people_count} people to {output_db}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
