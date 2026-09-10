"""
Regenerate farmingdale_courses.ndjson from the live college catalog.

    curl -A "RamHub-capstone/1.0" \
      -o fsc_catalog.html \
      https://www.farmingdale.edu/course-offerings/catalog_2025_2026.html
    python scrape_catalog.py

This is a data-prep tool, not part of the app — the committed .ndjson is what
`manage.py import_catalog` reads. Run it when a new catalog year is published,
then review the diff before committing.

Source: the whole catalog is a single static HTML page, so refreshing it is one
request. farmingdale.edu/robots.txt permits this (Crawl-Delay: 5, nothing
disallowing /course-offerings/); with one request per year that limit is moot.

Parsing notes worth keeping:
- Departments are <th class="active"> anchors; courses are <p><a name="CSC111">.
- Labels are punctuated inconsistently in the source ("Prerequisite(s):",
  "Prerequisite (s):", "Prerequisite(s)" with no colon, "Prerequisite(s);"), so
  LABEL_RE matches them anchored to the start of a line. Anchoring matters: some
  descriptions legitimately say "may be taken as a Prerequisite or Corequisite"
  mid-sentence, and that text belongs in the description.
- 23 courses have no "Credits:" line at all, only lecture/lab hours like "(1,0)".
  Those are NOT credits, so credits is left null rather than guessed.
"""

import html as htmlmod
import json
import re
import sys
from pathlib import Path

SRC = Path("fsc_catalog.html")
raw = SRC.read_text(errors="replace")

# Department headers: <th class="active" ...><a name="AET" id="AET">Automotive Technology</a>
DEPT_RE = re.compile(
    r'<th[^>]*class="active"[^>]*>.*?<a[^>]+name="([A-Z]{2,4})"[^>]*>(.*?)</a>',
    re.S | re.I,
)
# Course blocks: <p><a name="AET101">AET 101 - Title</a><br/> body </p>
COURSE_RE = re.compile(
    r'<p>\s*<a[^>]+name="([A-Z]{2,4}\d{3}[A-Z]?)"[^>]*>(.*?)</a>\s*<br\s*/?>(.*?)</p>',
    re.S | re.I,
)


def clean(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = htmlmod.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


# Where each department starts, so a course can be attributed to one.
dept_spans = [(m.start(), m.group(1), clean(m.group(2))) for m in DEPT_RE.finditer(raw)]
print(f"departments found: {len(dept_spans)}", file=sys.stderr)


def dept_for(pos: int):
    current = ("", "")
    for start, prefix, name in dept_spans:
        if start <= pos:
            current = (prefix, name)
        else:
            break
    return current


# The catalog punctuates these labels inconsistently: "Prerequisite(s):",
# "Prerequisite (s):", "Prerequisite(s)" with no colon, and "Prerequisite(s);"
# all occur. Matching a regex anchored to the start of a line handles every
# variant and, crucially, does NOT match the same words used mid-sentence —
# BCS 215's description really does say "may be taken as a Prerequisite or
# Corequisite", and that belongs in the description.
# Pre/Corequisite labels appear with and without punctuation ("Prerequisite(s):"
# and bare "Prerequisite(s) BIO 131" both occur), so their colon is optional.
# "Recommended" and "Credits" REQUIRE one: BIO 380's description genuinely opens
# with "Recommended students will engage in...", and without the colon
# requirement that sentence is mistaken for a label and the description is lost.
LABEL_RE = re.compile(
    r"(?m)^[ \t]*(?:"
    r"(Pre\s*(?:or|/|-)\s*Corequisites?\s*\(?s?\)?"
    r"|Prerequisites?\s*\(?s?\)?"
    r"|Corequisites?\s*\(?s?\)?"
    r")[ \t]*[:;]?"
    r"|(Recommended(?:\s+Prerequisites?\s*\(?s?\)?)?|Credits|Cross-listed)[ \t]*[:;]"
    r")[ \t]*"
)


def _label_text(match: re.Match) -> str:
    return (match.group(1) or match.group(2) or "").strip()


def split_body(body: str):
    """Separate the description from the trailing metadata lines."""
    text = clean(body)
    match = LABEL_RE.search(text)
    if not match:
        return text.strip(), ""
    return text[: match.start()].strip(), text[match.start() :].strip()


def field(meta: str, pattern: str) -> str:
    """Value of one label, up to the next label or end of the metadata block."""
    for match in LABEL_RE.finditer(meta):
        if re.fullmatch(pattern, _label_text(match), re.I):
            rest = meta[match.end() :]
            nxt = LABEL_RE.search(rest)
            value = rest[: nxt.start()] if nxt else rest
            return re.sub(r"\s+", " ", value).strip()
    return ""


def parse_credits(meta: str):
    m = re.search(r"Credits:\s*([0-9]+(?:\.[0-9]+)?)(?:\s*-\s*([0-9]+(?:\.[0-9]+)?))?", meta)
    if not m:
        return None, ""
    low = float(m.group(1))
    raw_text = m.group(0).replace("Credits:", "").strip()
    if m.group(2):
        raw_text = f"{m.group(1)}-{m.group(2)}"
        return int(float(m.group(1))), raw_text
    return int(low), raw_text


records, seen = [], set()
for m in COURSE_RE.finditer(raw):
    anchor, heading, body = m.group(1), clean(m.group(2)), m.group(3)
    heading = re.sub(r"\s+", " ", heading)
    hm = re.match(r"^([A-Z]{2,4}\s?\d{3}[A-Z]?)\s*[-–—]\s*(.+)$", heading)
    if not hm:
        continue
    code = re.sub(r"\s+", " ", hm.group(1)).strip()
    if " " not in code:
        code = re.sub(r"^([A-Z]{2,4})(\d.*)$", r"\1 \2", code)
    title = hm.group(2).strip()
    if code in seen:
        continue
    seen.add(code)

    description, meta = split_body(body)
    credits, credits_text = parse_credits(meta)
    prefix, dept_name = dept_for(m.start())

    records.append(
        {
            "code": code,
            "subject": code.split(" ")[0],
            "title": title,
            "description": description,
            "credits": credits,
            "credits_text": credits_text,
            "prerequisites": field(meta, r"Prerequisites?\s*\(?s?\)?"),
            "corequisites": field(meta, r"Corequisites?\s*\(?s?\)?"),
            "recommended": field(meta, r"Recommended.*"),
            "department": dept_name or prefix,
            "department_code": prefix,
            "catalog_year": "2025-2026",
            "source": "farmingdale.edu/course-offerings/catalog_2025_2026.html",
        }
    )

print(f"courses parsed: {len(records)}", file=sys.stderr)
Path("farmingdale_courses.ndjson").write_text(
    "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
)
