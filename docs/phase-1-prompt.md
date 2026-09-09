# Phase 1 — The catalog: Course and Professor, seeded and browsable

Paste everything below the line into Claude Code (or hand it to whoever picks up the
task). It assumes Phase 0 is merged: the Django + MongoDB scaffold, the design system at
`/styleguide`, and the seven nav tabs rendering placeholder pages.

---

## Context

Read `CLAUDE.md` first — it is the contract for this project, and Phase 1 is the first
phase that actually writes models, so its MongoDB section matters more here than anywhere
else so far.

Where the project stands after Phase 0:

- `apps/*/models.py` are all **empty files**. No collections exist beyond Django's own
  `admin` / `auth` / `contenttypes`, which migrate cleanly against MongoDB via
  `config/mongo_apps.py` and `mongo_migrations/`.
- `apps/catalog/views.py` renders `catalog/courses.html` and `catalog/professors.html`,
  and both templates are a `page_header` plus an `empty_state` that says the directory is
  not seeded yet.
- The design system is done and is not up for renegotiation: tokens in
  `static/src/input.css`, shared classes (`.row-link`, `.card`, `.rating-value`,
  `.badge-*`, `.field-input`, `.btn-*`, `.htmx-indicator`), partials
  (`partials/page_header.html`, `partials/empty_state.html`, `partials/icons/*`).
- Tests are routing/template smoke tests only. Nothing has touched the database yet, and
  CI has no MongoDB service (there is a comment in `.github/workflows/ci.yml` saying to
  add one when Phase 1 lands — that is now).

## What Phase 1 is

**The knowledge base gets its spine: `Course` and `Professor` exist, are seeded with
realistic demo data, and are browsable and searchable through the two directory pages and
a detail page each.**

That is the whole phase. It is deliberately the piece that everything else hangs off:
ratings attach to these two models, advice threads attach to these two models, the filing
cabinet saves these two models, and the assistant indexes them.

## What Phase 1 is not — do not build ahead

Auth arrives in Phase 2 and the community feed in Phase 3, so **anything requiring a
`User` is out of scope**:

- No `CourseRating` / `ProfessorRating` models, no rating forms, no write path for
  ratings. Phase 1 only *displays* the denormalized `rating_summary` that the seed
  command writes.
- No custom `User` model, no login, no `LoginRequiredMixin`. These pages are public for
  now; Phase 2 puts them behind the college-email gate.
- No posts, comments, votes, saved items, campus content, moderation, or assistant.
- No global search across posts and people. Phase 1 searches **within** each directory
  only. The nav search box stays a placeholder.
- No section/CRN data, no schedules, no seat counts.

If something in this list feels necessary to finish the phase, stop and say so instead of
building it.

## Models

Follow the data model in `CLAUDE.md` exactly. Only these two, plus the embedded summary:

```
Course
  code(unique, indexed), title, description, credits, department, prereq_text
  professor_ids: ArrayField(ObjectIdField)          # M2M replacement — no ManyToManyField
  rating_summary: Emb(avg_difficulty, avg_workload, avg_usefulness, count)

Professor
  first_name, last_name, department, title, photo, bio
  course_ids: ArrayField(ObjectIdField)
  rating_summary: Emb(avg_clarity, avg_helpfulness, avg_fairness, count)
```

Constraints that apply, all of them already written down in `CLAUDE.md`:

- `ObjectIdAutoField` primary keys (`DEFAULT_AUTO_FIELD` covers `apps.*`, so you get this
  for free — but confirm it in the generated migration rather than assuming).
- The two `rating_summary` fields are `EmbeddedModelField`s. **Get their shape right the
  first time**: updating an embedded model's indexes after the collection exists is
  unsupported, and existing documents are never rewritten by a migration. A `count` of 0
  and null averages is the correct "nobody has rated this yet" state — decide that now,
  not later.
- The two-way link between Course and Professor is `ArrayField(ObjectIdField)` on both
  sides, resolved with a single `filter(pk__in=...)`. No `ForeignKey`, no
  `ManyToManyField`, no `$lookup`.
- Denormalized fields are never recomputed with a live aggregation on a list page. In
  Phase 1 nothing recomputes them at all — the seed command writes them.
- Indexes: `code` unique, plus whatever the directory queries actually sort and filter on
  (`department`, `last_name`). Declare them in `Meta.indexes` / `Meta.constraints` and
  justify each one in the PR — do not add speculative indexes.

Register both models in `apps/catalog/admin.py` with list displays that are usable for
checking seeded data.

**Before writing any of this, check the current `django-mongodb-backend` docs** for the
exact import paths and field signatures (`ArrayField`, `ObjectIdField`,
`EmbeddedModelField`, index support): the package is new and most of what an LLM
remembers about it is wrong.
https://www.mongodb.com/docs/languages/python/django-mongodb/current/

## `python manage.py seed_demo`

`CLAUDE.md` promises this command arrives in Phase 1. Put it in
`apps/catalog/management/commands/seed_demo.py`.

- **Idempotent.** Running it twice leaves the database in the same state as running it
  once — key on the natural key (`Course.code`, and professor name + department). A
  teammate should be able to run it on a database that already has data without producing
  duplicates.
- **Realistic.** Around 50–70 real Farmingdale course codes across several departments
  (CSC, MTH, EGL, BUS, BIO, PSY, HIS, ARC is a reasonable spread), and 25–35 professors,
  each linked to the courses they teach in **both** directions. Titles, credits, and
  prerequisite text should read like a real catalog, because these pages are what the
  team demos.
- **Rated.** Seed `rating_summary` with plausible spread — some courses genuinely hard,
  some easy, and a few with `count = 0` so the "no ratings yet" state is visible on a real
  page and not just in theory.
- **Sourced.** Keep the fixture data in a separate module or JSON file rather than a
  1,000-line command, and say in a comment where it came from and that it is
  representative, not authoritative.
- Print a summary of what it created versus updated. Support `--clear` only if you keep it
  obviously destructive and guarded.

## Pages

Business logic goes in `apps/catalog/services.py`. Views parse the request, call a
service, render. Query parameters are validated by a **Django form** — no reading
`request.GET[...]` by hand.

### Courses directory — `/courses/`

- Dense, scannable rows using `.row-link`. Per row: code, title, department, credits, and
  the rating summary as the visual anchor (a number plus a compact bar or dot scale —
  never stars).
- Search box filtering on code and title, and a department filter. Sort by code, by
  rating, by number of ratings.
- HTMX: typing in the search box swaps the results region (`hx-get`, debounced ~300ms,
  `hx-push-url` so the result is linkable and the back button works). The form must still
  work as a plain GET with JavaScript off — build it that way and then layer HTMX on top.
- Pagination at 25 per page, with a "Load more" that appends the next page. Give it a real
  `.htmx-indicator`.
- The empty state now means **"your search matched nothing"**, with a way back to the full
  list — not "the directory is not seeded yet". Delete that placeholder.

### Professors directory — `/professors/`

Same shape: rows with name, title, department, and the clarity/helpfulness/fairness
summary; search by name; filter by department; the same pagination and HTMX behavior.
Reuse the row and results partials where the two directories genuinely share structure —
`templates/partials/` — but do not contort one template to serve both.

### Course detail — `/courses/<code>/`

Header with code, title, department, credits, and the rating summary rendered large.
Description and prerequisites. **Professors who teach it**, resolved from
`professor_ids` in one query, each linking to their detail page. Then a placeholder region
for advice and ratings, honestly labeled as arriving in a later phase — a real empty state
with an explanation, not a dead button.

The context processor's active-tab rule already assumes this URL shape
(`/courses/CSC-240/` keeps the Courses tab lit) — verify that still holds.

### Professor detail — `/professors/<pk>/`

Header with name, title, department, and the summary. Bio. **Courses they teach**,
resolved from `course_ids` in one query. Same honest placeholder for ratings and advice.

Unknown code or id is a 404, not a crash.

## Tests

`pytest` + `pytest-django`, in `apps/catalog/tests/`. At minimum:

- Model round-trip against MongoDB: create a Course, read it back, confirm the `ObjectId`
  pk and the embedded `rating_summary`.
- The unique constraint on `Course.code` actually rejects a duplicate.
- Each service function: search matches code and title, department filter, each sort
  order, and the two-way `professor_ids` / `course_ids` resolution.
- Views: both directories return 200 and contain a seeded course/professor; a search with
  no matches renders the empty state; an unknown course code 404s.
- `seed_demo` is idempotent — run it twice, assert the counts are identical.

Two things to work out rather than guess:

1. How `pytest-django`'s database fixtures behave against `django_mongodb_backend` —
   whether the standard `django_db` mark's transaction wrapping works, or whether these
   tests need `django_db(transaction=True)`. Verify it, then leave a comment in
   `conftest.py` explaining what you found so the next person does not rediscover it.
2. **CI has no MongoDB.** `.github/workflows/ci.yml` needs a service container now.
   Transactions need a replica set, so a plain `mongo` service is not automatically
   enough — either initiate a single-node replica set as a step, or use an image that
   ships as one. Prove it by watching CI go green, not by reasoning about it.

## Also update

- `apps/catalog/views.py` — the "Seeded from the catalog in Phase 1" docstrings are now
  wrong.
- `README.md` — `seed_demo` in the setup steps (it is what makes a fresh clone show
  something), and any change to how tests are run locally against MongoDB.
- `CLAUDE.md` — only if Phase 1 discovers that something documented there is wrong, the
  way Phase 0 did. Corrections are welcome; additions of new opinion are not.

## Definition of done

The list in `CLAUDE.md` applies in full, and specifically:

- Works at 375px. The directory rows are the hard case — check them there first, not last.
- Keyboard navigable with visible focus rings, including the HTMX search and "Load more".
- Loading, empty, and error states all real and all reachable.
- Every query parameter validated through a Django form.
- No hardcoded colors, sizes, or radii — add a token in `static/src/input.css` if a
  utility is missing, and show it on `/styleguide`.
- `ruff check . && ruff format --check . && pytest` passes locally and in CI.
- Run axe on both directories and both detail pages.

## How to work

Commit in reviewable pieces — models and migration, then the seed command, then the
directories, then the detail pages — rather than one commit at the end. Say plainly in
each commit message what you verified and how, in the style of the Phase 0 commits. If
you hit a `django-mongodb-backend` behavior that contradicts what we wrote down, that
finding is worth as much as the feature; write it up.
