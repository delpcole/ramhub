# Farmingdale State College — RateMyProfessors Dataset

Data documentation for every professor listed for **Farmingdale State College**
(RateMyProfessors school ID `14046`) on ratemyprofessors.com.

- **Collected:** 2026-09-10
- **Source:** ratemyprofessors.com public GraphQL API (`https://www.ratemyprofessors.com/graphql`)
- **Method:** Paginated `newSearch.teachers` query scoped to `schoolID = School-14046`, 100 records/page, de-duplicated by `legacyId`. See `fetch_profs.py` for the exact script.
- **Records:** 1,634 professors (1,459 with at least one rating, 175 with none)
- **Files:**
  - `farmingdale_professors.csv` — flat table, one row per professor
  - `farmingdale_professors.json` — same records with full (un-truncated) course lists
  - `fetch_profs.py` — reproducible collection script

---

## How the data was obtained

The public [`RateMyProfessorAPI`](https://github.com/Nobelz/RateMyProfessorAPI)
PyPI package (`pip install RateMyProfessorAPI`) only supports **name-based**
lookups (`get_professor_by_school_and_name`) and has no "list all professors"
call. To enumerate the entire faculty, `fetch_profs.py` calls the same
undocumented GraphQL endpoint the package uses, but with the site's
`newSearch.teachers` query and cursor pagination:

```
query ($query: TeacherSearchQuery!, $count: Int!, $cursor: String) {
  search: newSearch {
    teachers(query: $query, first: $count, after: $cursor) {
      resultCount
      pageInfo { hasNextPage endCursor }
      edges { node { id legacyId firstName lastName department
                     avgRating avgDifficulty numRatings
                     wouldTakeAgainPercent courseCodes { courseName courseCount } } }
    }
  }
}
```

with `variables.query = { text: "", schoolID: "U2Nob29sLTE0MDQ2", fallback: false }`
(`U2Nob29sLTE0MDQ2` is base64 for `School-14046`). The request needs the header
`Authorization: Basic dGVzdDp0ZXN0` (the site's hard-coded public credential).

To refresh the dataset:

```bash
python -m pip install requests
python fetch_profs.py
```

---

## Column dictionary (`farmingdale_professors.csv`)

| Column | Type | Description | Notes / caveats |
|---|---|---|---|
| `last_name` | string | Professor surname as entered on RMP | User-submitted; some entries are misspelled, duplicated, or contain titles ("Dr."). Leading/trailing whitespace is stripped by the script. |
| `first_name` | string | Professor given name as entered on RMP | Same caveats as `last_name`. A few records repeat the surname here. |
| `department` | string | Department label assigned on RMP | RMP's own taxonomy, **not** Farmingdale's official department names. 70 distinct values. Similar areas are sometimes split (e.g. `Computer Science`, `Computer Information Systems`, `Computer & Information Systems`). Never empty in this pull. |
| `avg_rating` | float (1.0–5.0) | Mean "quality" score across all student ratings | Empty when `num_ratings = 0`. Higher = better. |
| `avg_difficulty` | float (1.0–5.0) | Mean difficulty score across all student ratings | Empty when `num_ratings = 0`. Higher = harder. |
| `num_ratings` | integer | Count of individual student ratings behind the averages | `0` for 175 professors (newly listed or never rated). Ranges 0–226. |
| `would_take_again_pct` | float (0–100) | % of raters who said they would take the professor again | Empty when RMP has no data (value `-1`/`null` upstream). Populated for 1,226 professors. |
| `top_courses` | string | Up to 5 most-rated course codes, `CODE (n)` where `n` = ratings for that course, `;`-separated | Course codes are free-text and inconsistently formatted (`PSY101`, `PSY 101`, `psy-101`). Full list is in the JSON file. |
| `legacy_id` | integer | RMP's stable numeric professor ID | Primary key. Stable across pulls. |
| `profile_url` | string | `https://www.ratemyprofessors.com/professor/<legacy_id>` | Direct link to the public profile. |

The JSON file contains the same fields plus the **complete** `courseCodes`
array (`[{courseName, courseCount}, ...]`) and the GraphQL node `id`.

---

## Dataset summary

| Metric | Value |
|---|---|
| Professors listed | 1,634 |
| — with ≥1 rating | 1,459 (89%) |
| — with 0 ratings | 175 (11%) |
| Total individual student ratings | 26,680 |
| Distinct departments (RMP taxonomy) | 70 |
| Mean `avg_rating` (rated professors) | 3.71 / 5.0 |
| Median `avg_rating` | 4.0 / 5.0 |
| Mean `avg_difficulty` | 2.80 / 5.0 |
| Mean `would_take_again_pct` (n=1,226) | 67.3% |
| Most-rated professor | Karen Bottalico (Psychology) — 226 ratings, 4.9 |

### Rating distribution (rated professors)

| Band | Professors |
|---|---|
| 1.0–1.9 | 140 |
| 2.0–2.9 | 230 |
| 3.0–3.9 | 330 |
| 4.0–4.9 | 545 |
| 5.0 | 214 |

Many 5.0 scores come from professors with only 1–2 ratings — filter on
`num_ratings` before ranking.

### Largest departments (by professor count)

| Department | Professors |
|---|---|
| English | 151 |
| Biology | 137 |
| Business | 133 |
| Mathematics | 93 |
| Psychology | 91 |
| Criminal Justice | 77 |
| Sociology | 73 |
| Engineering | 70 |
| Nursing | 59 |
| History | 54 |

### Most-rated professors

| Professor | Department | Avg rating | Ratings |
|---|---|---|---|
| Karen Bottalico | Psychology | 4.9 | 226 |
| Jill O'Sullivan | Business | 4.0 | 171 |
| Bindu Dulock | Psychology | 4.7 | 162 |
| Richard Marsillo | Biology | 4.7 | 134 |
| Laurie Rozakis | English | 4.0 | 133 |
| Kenneth Hershkoff | Biology | 4.7 | 121 |
| Harry Espaillat | Computer Information Systems | 4.5 | 118 |
| Rich Freda | Mathematics | 4.9 | 114 |
| Marla Johnston | Psychology | 4.4 | 113 |
| Robert Saunders | History | 2.9 | 111 |

---

## Known limitations

1. **Self-selected, non-representative sample.** RMP ratings are submitted
   voluntarily by students; they are not a survey and skew toward strong
   opinions. Treat as anecdote-scale data, not an evaluation instrument.
2. **Historical accumulation.** The list includes former and adjunct faculty
   who may no longer teach at Farmingdale. There is no "active" flag and no
   term/year on the aggregate record (individual ratings carry dates —
   retrievable per professor via the API's ratings query).
3. **Free-text quality.** Names, departments, and course codes are
   user-entered and inconsistent. Duplicate professor entries exist where
   students created a second profile instead of finding the first.
4. **No tag data.** RMP's "teacher tags" (e.g. *Tough grader*, *Caring*) are
   not returned by the search endpoint; collecting them requires one
   additional API call per professor (~1,634 requests). Ask if you want the
   dataset enriched with tags and per-rating comments.
5. **Unofficial API.** The endpoint is undocumented and unauthenticated; its
   schema or the public credential can change without notice.
6. **Terms of use.** This is scraped public data. Use for personal/research
   purposes; do not redistribute commercially.
