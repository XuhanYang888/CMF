#!/usr/bin/env python3

"""Extract contest honour-roll rows from Euclid, CSMC, CIMC, or Pascal exports.

Usage:
        python scraper.py [contest] [input_file] [output_csv]

Contest values:
        euclid - Euclid Student Honour Roll HTML exports
        csmc   - CSMC Student Honour Roll HTML exports
        cimc   - CIMC Student Honour Roll HTML exports
    pascal - Pascal Student Honour Roll HTML exports

If contest is omitted, Euclid is assumed for backward compatibility.
"""

from __future__ import annotations

import csv
import html
import re
import sys
from functools import lru_cache
from pathlib import Path


DIV_RE = re.compile(
    r'<div class="(?P<class>[^"]*\bt\b[^"]*)"[^>]*>(?P<body>.*?)</div>', re.DOTALL
)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")

GROUP_RE = re.compile(
    r"Group\s+([IVX]+)\s*/\s*Groupe\s+[IVX]+\s+Scores/Notes\s+([0-9]+\s*-\s*[0-9]+)",
    re.IGNORECASE,
)
GRADE_RE = re.compile(r"^(?P<body>.*)\s(?P<grade>[0-9]{1,2})$")
SCHOOL_ABBREV_RE = re.compile(r"^(?:[A-Za-z]\.){2,}[A-Za-z]?\.?$")

SCHOOL_END_KEYWORDS = {
    "school",
    "schools",
    "sch",
    "schoo",
    "h.s",
    "s.s",
    "d.h.s",
    "c.i",
    "c.h.s",
    "c.s.s",
    "c.s.c",
    "c.a",
    "college",
    "academy",
    "campus",
    "institute",
    "institut",
    "lyceum",
    "ms",
    "m.s",
    "high",
    "secondary",
}

CANADIAN_MUNICIPALITIES = {
    "abbotsford",
    "ajax",
    "ancaster",
    "aurora",
    "barrie",
    "bedford",
    "belleville",
    "brampton",
    "brandon",
    "brantford",
    "brossard",
    "burlington",
    "burnaby",
    "calgary",
    "cambridge",
    "candiac",
    "charlottetown",
    "chatham",
    "coquitlam",
    "courtenay",
    "dartmouth",
    "delta",
    "dollard des ormeaux",
    "duncan",
    "dunrobin",
    "edmonton",
    "etobicoke",
    "fredericton",
    "gatineau",
    "gloucester",
    "guelph",
    "halifax",
    "hamilton",
    "hope",
    "kamloops",
    "kanata",
    "kelowna",
    "king city",
    "kingston",
    "kirkland",
    "kitchener",
    "la prairie",
    "lachine",
    "lakefield",
    "langley",
    "lasalle",
    "laval",
    "london",
    "maple",
    "maple ridge",
    "markham",
    "milton",
    "mississauga",
    "moncton",
    "montreal",
    "montreal-ouest",
    "nanaimo",
    "nelson",
    "nepean",
    "new westminster",
    "newmarket",
    "niagara falls",
    "niagara-on-the-lake",
    "north vancouver",
    "north york",
    "oakville",
    "okotoks",
    "oshawa",
    "ottawa",
    "owen sound",
    "parksville",
    "parry sound",
    "pitt meadows",
    "pointe-claire",
    "port coquitlam",
    "port elgin",
    "port hope",
    "port moody",
    "quebec",
    "regina",
    "revelstoke",
    "richmond",
    "saskatoon",
    "richmond hill",
    "rockcliffe",
    "rosseau",
    "rothesay",
    "saint john",
    "saint-lambert",
    "saint-laurent",
    "sainte-anne-de-belle",
    "scarborough",
    "shawnigan lake",
    "sherbrooke",
    "st catharines",
    "st john's",
    "st johns",
    "stoney creek",
    "stouffville",
    "surrey",
    "thornhill",
    "toronto",
    "vancouver",
    "vaughan",
    "vernon",
    "victoria",
    "waterdown",
    "waterloo",
    "welland",
    "west vancouver",
    "westmount",
    "whitby",
    "whitchurch-stouffvil",
    "windsor",
    "winnipeg",
    "wolfville",
    "woodbridge",
    "york",
}

CANADIAN_PROVINCES = {
    "ab",
    "alberta",
    "bc",
    "british columbia",
    "mb",
    "manitoba",
    "nb",
    "new brunswick",
    "nl",
    "newfoundland and labrador",
    "ns",
    "nova scotia",
    "nt",
    "northwest territories",
    "nu",
    "nunavut",
    "on",
    "ontario",
    "pe",
    "pei",
    "prince edward island",
    "qc",
    "quebec",
    "sk",
    "saskatchewan",
    "yt",
    "yukon",
}

CANADIAN_MUNICIPALITIES_FILE = Path(__file__).with_name("canadian_municipalities.txt")

CONTEST_TO_DIR = {
    "euclid": "Euclid",
    "csmc": "CSMC",
    "cimc": "CIMC",
    "pascal": "Pascal",
}

CONTESTS = set(CONTEST_TO_DIR)


def normalize_place(text: str) -> str:
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    text = re.sub(r"[.,;:]", " ", text)
    return SPACE_RE.sub(" ", text.lower()).strip()


@lru_cache(maxsize=1)
def load_canadian_municipalities() -> set[str]:
    if not CANADIAN_MUNICIPALITIES_FILE.exists():
        return set()

    with CANADIAN_MUNICIPALITIES_FILE.open(encoding="utf-8") as f:
        return {normalize_place(line) for line in f if normalize_place(line)}


def is_known_canadian_municipality(place: str) -> bool:
    place = normalize_place(place)
    if not place:
        return False
    if place in CANADIAN_MUNICIPALITIES:
        return True
    return place in load_canadian_municipalities()


def looks_like_school_abbrev(token: str) -> bool:
    token = token.strip(" .,;:")
    if not token:
        return False
    if SCHOOL_ABBREV_RE.match(token):
        return True
    return normalize_place(token) in SCHOOL_END_KEYWORDS


def is_canadian_location_tokens(tokens: list[str]) -> bool:
    if not tokens:
        return False
    if looks_like_school_abbrev(tokens[0]):
        return False

    location = normalize_place(" ".join(tokens))
    if is_known_canadian_municipality(location):
        return True

    if len(tokens) >= 2:
        province = normalize_place(tokens[-1])
        city = normalize_place(" ".join(tokens[:-1]))
        if province in CANADIAN_PROVINCES and is_known_canadian_municipality(city):
            return True

    return False


def clean_div_text(raw_div_body: str) -> str:
    text = TAG_RE.sub(" ", raw_div_body)
    text = html.unescape(text)
    text = text.replace("\ue609", " ")
    text = SPACE_RE.sub(" ", text).strip()
    return text


def split_school_and_location(tokens: list[str]) -> tuple[str, str]:
    if not tokens:
        return "", ""
    if len(tokens) == 1:
        single = tokens[0].strip()
        if is_known_canadian_municipality(single):
            return "", single
        return single, ""

    # Allow matching the full token list as a location so rows with no school
    # (e.g., "Richmond Hill") are parsed as location-only.
    max_suffix = min(4, len(tokens))
    for suffix_len in range(max_suffix, 0, -1):
        location_tokens = tokens[-suffix_len:]
        if is_canadian_location_tokens(location_tokens):
            school_tokens = tokens[:-suffix_len]
            # If the token right before location is a school abbreviation
            # (e.g., "Sch"), keep it with the school name.
            if school_tokens and looks_like_school_abbrev(school_tokens[-1]):
                continue
            return " ".join(school_tokens).strip(), " ".join(location_tokens).strip()

    split_at = None
    for idx, token in enumerate(tokens):
        normalized = token.lower().strip(".,")
        if normalized in SCHOOL_END_KEYWORDS:
            split_at = idx

    if split_at is not None and split_at < len(tokens) - 1:
        school = " ".join(tokens[: split_at + 1]).strip()
        location = " ".join(tokens[split_at + 1 :]).strip()
        return school, location

    if len(tokens) >= 4:
        return " ".join(tokens[:-2]).strip(), " ".join(tokens[-2:]).strip()
    return " ".join(tokens[:-1]).strip(), tokens[-1].strip()


def parse_euclid_or_csmc_row_text(row_text: str) -> tuple[str, str, str, str] | None:
    row_text = row_text.strip()
    grade_match = GRADE_RE.match(row_text)
    if not grade_match:
        return None

    grade = grade_match.group("grade")
    body = grade_match.group("body").strip()
    parts = body.split()
    if len(parts) < 3:
        return None

    name_tokens = parts[:2]
    rest_tokens = parts[2:]
    name = " ".join(name_tokens).strip()
    school, location = split_school_and_location(rest_tokens)
    return name, school, location, grade


def extract_html_rows(html_text: str, row_class_token: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    in_student_section = False
    current_group = ""
    current_score_range = ""
    current_category = ""

    for match in DIV_RE.finditer(html_text):
        class_attr = match.group("class")
        div_text = clean_div_text(match.group("body"))
        if not div_text:
            continue

        if "Student Honour Roll/Palmarès d'étudiants" in div_text:
            in_student_section = True
            current_group = ""
            current_score_range = ""
            current_category = "Canadian"
            continue

        if "Team Honour Roll/Palmarès d'équipes" in div_text:
            if in_student_section:
                break
            continue

        if not in_student_section:
            continue

        if div_text == "International":
            current_category = "International"
            continue

        if (
            "Name/Nom" in div_text
            or "School/École" in div_text
            or "Location/Endroit" in div_text
            or "Grade/Niveau" in div_text
        ):
            continue

        group_match = GROUP_RE.search(div_text)
        if group_match:
            current_group = group_match.group(1)
            current_score_range = group_match.group(2)
            continue

        if row_class_token not in class_attr:
            continue

        parsed = parse_euclid_or_csmc_row_text(div_text)
        if not parsed:
            continue

        name, school, location, grade = parsed
        if current_category != "Canadian":
            continue

        rows.append(
            {
                "category": current_category,
                "group": current_group,
                "score_range": current_score_range,
                "name": name,
                "school": school,
                "location": location,
                "grade": grade,
                "raw_text": div_text,
            }
        )

    return rows


def extract_euclid_rows(html_text: str) -> list[dict[str, str]]:
    return extract_html_rows(html_text, "fs7")


def extract_csmc_rows(html_text: str) -> list[dict[str, str]]:
    return extract_html_rows(html_text, "h3")


def extract_cimc_rows_from_html(html_text: str) -> list[dict[str, str]]:
    return extract_html_rows(html_text, "h3")


def extract_pascal_rows_from_html(html_text: str) -> list[dict[str, str]]:
    return extract_html_rows(html_text, "h3")


def write_csv(rows: list[dict[str, str]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "category",
        "group",
        "score_range",
        "name",
        "school",
        "location",
        "grade",
        "raw_text",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def contest_data_dir(contest: str) -> Path:
    return Path("contest_data") / CONTEST_TO_DIR.get(contest, contest.capitalize())


def default_input_path(contest: str) -> Path:
    html_dir = contest_data_dir(contest) / "html"
    if html_dir.is_dir():
        html_files = sorted(html_dir.glob("*.html")) + sorted(html_dir.glob("*.htm"))
        if len(html_files) == 1:
            return html_files[0]
        for html_file in html_files:
            if contest in html_file.stem.lower():
                return html_file
        if html_files:
            return html_files[0]
    return Path(f"{contest}.html")


def default_output_path(contest: str) -> Path:
    return contest_data_dir(contest) / "csv" / f"{contest}_student_honour_roll.csv"


def parse_args(argv: list[str]) -> tuple[str, Path, Path]:
    contest = "euclid"
    args = list(argv)
    if args and args[0].lower() in CONTESTS:
        contest = args.pop(0).lower()

    input_path = Path(args[0]) if args else default_input_path(contest)
    output_path = Path(args[1]) if len(args) > 1 else default_output_path(contest)
    return contest, input_path, output_path


def main(argv: list[str] | None = None) -> int:
    contest, input_path, output_path = parse_args(
        sys.argv[1:] if argv is None else argv
    )

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 1

    if input_path.suffix.lower() not in {".html", ".htm"}:
        print("All contests require HTML input files (.html or .htm).")
        return 1

    if contest in {"euclid", "csmc"}:
        html_text = input_path.read_text(encoding="utf-8", errors="replace")
        rows = (
            extract_euclid_rows(html_text)
            if contest == "euclid"
            else extract_csmc_rows(html_text)
        )
    elif contest == "cimc":
        html_text = input_path.read_text(encoding="utf-8", errors="replace")
        rows = extract_cimc_rows_from_html(html_text)
    elif contest == "pascal":
        html_text = input_path.read_text(encoding="utf-8", errors="replace")
        rows = extract_pascal_rows_from_html(html_text)
    else:
        print(f"Unsupported contest: {contest}")
        return 1

    write_csv(rows, output_path)
    print(f"Wrote {len(rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
