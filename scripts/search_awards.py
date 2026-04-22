#!/usr/bin/env python3

"""Search the Euclid awards database by name.

Usage:
	python search_awards.py [search_term]

If no search term is provided, you'll be prompted to enter one interactively.
Shows all people whose names contain the search term (case-insensitive),
along with their awards, years, score ranges, and grades.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


DEFAULT_DB = Path("contest_data/awards.sqlite3")


def search_people(db_path: Path, search_term: str) -> None:
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    search_term = search_term.strip()
    if not search_term:
        print("Search term cannot be empty.")
        return

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        # Find people matching the search term
        people = conn.execute(
            "SELECT id, name FROM people WHERE name LIKE ? ORDER BY name",
            (f"%{search_term}%",),
        ).fetchall()

        if not people:
            print(f"No matches found for: {search_term}")
            return

        print(f"\nFound {len(people)} match(es) for '{search_term}':\n")

        for person in people:
            person_id = person["id"]
            name = person["name"]

            # Get all awards for this person
            awards = conn.execute(
                """
				SELECT year, score_range, grade, source_csv
				FROM awards
				WHERE person_id = ?
				ORDER BY year DESC
				""",
                (person_id,),
            ).fetchall()

            print(f"Name: {name}")
            print(f"Awards: {len(awards)}")
            for award in awards:
                print(
                    f"  • {award['year']}: {award['score_range']} (Grade {award['grade']}) [{award['source_csv']}]"
                )
            print()


def main() -> int:
    db_path = DEFAULT_DB

    if len(sys.argv) > 2:
        print("Usage: python search_awards.py [search_term]")
        return 1

    if len(sys.argv) > 1:
        search_term = sys.argv[1]
    else:
        search_term = input("Enter name to search (substring): ").strip()

    search_people(db_path, search_term)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
