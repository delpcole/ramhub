# Farmingdale State College — Directory Export

**File:** `farmingdale_directory.ndjson`
**Records:** 1,618 (one JSON object per line, UTF-8)
**Source:** https://www.farmingdale.edu/directory/ (public campus directory, static HTML table)
**Retrieved:** 2026-09-10

## Fields

| field | type | notes |
|---|---|---|
| `slug` | string | URL-safe `first-last`, lowercased, ASCII-folded. Unique across the file (collisions get a `-2` suffix). Stable key for a professor page. |
| `directory_name` | string | Raw "Last, First" as printed in the directory. |
| `display_name` | string | "First Last". |
| `first_name` / `last_name` | string | Split on the first comma; `last_name` may be multi-word. |
| `group` | string | `faculty`, `adjunct`, `staff`, or `faculty-staff`. |
| `is_teaching` | bool | true for `faculty`, `adjunct`, `faculty-staff`. Use this to filter the rate-my-professor list (913 true). |
| `title` | string\|null | Job title, e.g. "Adjunct Assistant Professor". |
| `department` | string\|null | 62 distinct departments among teaching staff. |
| `department_url` | string\|null | Link to the department page. |
| `faculty_id` | string\|null | Farmingdale's internal numeric id (`fid`). Present for most teaching staff. |
| `profile_url` | string\|null | `https://www.farmingdale.edu/faculty/?fid=<faculty_id>`. |
| `phone` | string\|null | Office phone. |
| `location` | string\|null | Building + room. |
| `source` / `source_retrieved` | string | Provenance. |

## Placeholder rating fields (all empty — to be filled by user reviews)

| field | type | initial |
|---|---|---|
| `rating_count` | int | `0` |
| `rating_avg` | float\|null | `null` (1–5 scale suggested) |
| `difficulty_avg` | float\|null | `null` (1–5 scale suggested) |
| `would_take_again_pct` | float\|null | `null` (0–100) |
| `tags` | string[] | `[]` |

## Notes for the downstream agent

- Emails are hashed on the source page and are **not** included.
- No ratings data from RateMyProfessors or any third party is included — these are directory facts only. Rating fields are meant to be populated from reviews submitted on this platform.
- `staff` rows (705) are included for completeness; filter with `is_teaching` if you only want professors.
- Re-scraping the source periodically will catch new hires / departures; match on `faculty_id` when present, else `slug`.
