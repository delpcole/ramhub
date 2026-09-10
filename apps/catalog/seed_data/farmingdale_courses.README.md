# Farmingdale State College — Course Catalog Export

**File:** `farmingdale_courses.ndjson`
**Records:** 1,785 (one JSON object per line, UTF-8)
**Source:** <https://www.farmingdale.edu/course-offerings/catalog_2025_2026.html>
**Catalog year:** 2025–2026
**Retrieved:** 2026-09-10
**Regenerate with:** `scrape_catalog.py` (see its docstring)

Real course data from the official published catalog — unlike the demo courses
this replaced, these are not invented.

## Fields

| field | type | notes |
|---|---|---|
| `code` | string | e.g. `CSC 229`. Unique. The natural key and the URL. |
| `subject` | string | Code prefix, e.g. `CSC`. 67 distinct. |
| `title` | string | Course title as printed. |
| `description` | string | Catalog description. Always present. |
| `credits` | int\|null | **Null for 23 courses** whose catalog entry has no `Credits:` line — only lecture/lab hours like `(1,0)`, which are not credits. Not guessed. |
| `credits_text` | string | Raw credits text, e.g. `3 (2,2)`. |
| `prerequisites` | string | Free text, as printed. 1,429 courses have one. |
| `corequisites` | string | Free text. 195 courses have one. |
| `recommended` | string | Free text. |
| `department` | string | Full department name from the section header. |
| `department_code` | string | Section prefix. |
| `catalog_year` | string | `2025-2026`. |

## Caveats

- **A published catalog is not a schedule.** It says a course exists, not that it
  runs this semester, and not who teaches it. Nothing here links a course to a
  professor; that needs real section/schedule data.
- Prerequisite text is free-form prose, not a parsed dependency graph.
- Re-scrape when a new catalog year is published, and match on `code`.
