# RamHub

A private, school-email-only community website for the students of **Farmingdale State
College**. Students look up any course or professor, read honest advice and ratings from
students who actually took it, and add their own. A community feed, campus-info tabs, saved
collections, and a mascot AI assistant sit around that core.

This is a semester-long university capstone project built by a team of six students. Favor
clarity and maintainability over cleverness — every teammate has to be able to read and
extend this code.

## The rule that settles design arguments

RamHub is a **knowledge base about courses and professors**, with a social layer that feeds
it. When there's a tradeoff, favor whatever makes course and professor advice easier to
find, read, and contribute. Social features are secondary and exist to grow the knowledge
base.

## Users and access

Verified Farmingdale State College students only. Sign-up requires an email address ending
in the college domain (`farmingdale.edu`, read from the `COLLEGE_EMAIL_DOMAIN` setting).

Roles: `STUDENT` (default), `MODERATOR`, `ADMIN`.

**Both directories hold real, official data.** ~1,785 courses come from the published
2025-26 catalog (`manage.py import_catalog`) and ~913 faculty from the public campus
directory (`manage.py import_directory`). There is no demo data left in either. Two rules
follow and are not negotiable:

- **Never invent a rating.** No demo ratings, no seeded averages, no numbers we made up.
  **Courses have no ratings at all** until a student leaves one.
- **Professor ratings are currently imported from RateMyProfessors**, by explicit decision.
  This is the single exception to the rule above, and it comes with conditions that are not
  optional:
  - Every imported number carries `rating_summary.source = "rmp"`, and **every place it is
    displayed says it came from RateMyProfessors**. Do not remove that attribution, and do
    not add a rating path that leaves `source` blank.
  - A rating a student leaves on RamHub always wins. `import_rmp` skips any professor whose
    summary is already `source="ramhub"`.
  - RMP's single "quality" score maps to `avg_overall` only. `avg_clarity` /
    `avg_helpfulness` / `avg_fairness` stay null — splitting one number into three would
    invent detail RMP does not have.
  - Only ~60% of directory staff match an RMP record. The rest correctly show no rating.
  - RMP data is scraped from an undocumented endpoint, is voluntary and self-selected, and
    its README says not to redistribute it commercially. Revisit this when RamHub has
    reviews of its own — the intent is a bridge, not a permanent feature.
- **Never assert a relationship we cannot verify.** A directory says who works here; a
  catalog says a course exists. Neither says who teaches what, so courses are not linked to
  professors. Guessing by department would put a real person's name on a course they may
  never have taught. That link waits for real section/schedule data.
- **"Highest rated" sorts on `rank_score`, not the raw average.** A 5.0 from one rating must
  not outrank a 4.9 from 226. `rank_score` is a stored Bayesian average; the displayed
  number stays the true average.

## Tech stack — fixed by the course, do not propose alternatives

- **Python 3.12+** (developed on 3.13)
- **Django 6.1** — server-rendered **Django templates** are the user interface.
- **Django REST Framework** — JSON endpoints under `/api/` for the interactive pieces the
  templates call (voting, search autocomplete, saving items, the AI assistant).
- **MongoDB** via **`django-mongodb-backend`** (MongoDB's official Django backend, GA).
  `ENGINE = "django_mongodb_backend"`. Use MongoDB Atlas.
  **Pinned: Django 6.1.1 + django-mongodb-backend 6.1.0.** The backend's X.Y must match
  Django's X.Y — it raises `ImproperlyConfigured` at import time otherwise. Upgrade both
  in the same PR or neither.
- **HTMX** for progressive interactivity inside templates (partial updates, infinite
  scroll, inline forms). Small amounts of vanilla JS only where HTMX doesn't fit. No React,
  no SPA framework.
- **GSAP 3.15 + ScrollTrigger + Lenis 1.3** — **landing page only** (`/`), for its scroll
  motion. Vendored in `static/vendor/` (see `VERSIONS.txt`) and loaded by `pages/home.html`
  alone; a test fails if they appear on any other page. Everything else stays htmx + vanilla
  JS. Motion must respect `prefers-reduced-motion` and the page must be complete with
  JavaScript off.
- **Tailwind CSS v4** via the standalone CLI (`npm run tailwind:watch`). Tokens live in
  `static/src/input.css`; the stock color and type scales are cleared on purpose, so add a
  token rather than hardcoding a value. Review the system at `/styleguide`.
- **Figma** for design mockups — implement what the design lead produces.
- **GitHub** for version control, **Kanban board** for task tracking.
- **Testing:** `pytest` + `pytest-django`. **Linting/format:** `ruff`.

Before writing code against Django, DRF, or `django-mongodb-backend`, check the current
official docs. `django-mongodb-backend` is new and its API is not in most training data:
https://www.mongodb.com/docs/languages/python/django-mongodb/current/

## MongoDB constraints that drive our design

`django-mongodb-backend` supports most of Django, but these limits shape our models. Respect
them — do not "fix" them by reaching for patterns that don't work here.

- **`AutoField` is unsupported.** Every model uses `ObjectIdAutoField` as its primary key.
  `DEFAULT_AUTO_FIELD` covers our apps but **does not reach Django's contrib apps** — they
  pin their own, so `auth.User`, `auth.Group`, `auth.Permission`, `admin.LogEntry`, and
  `contenttypes.ContentType` fail `manage.py check` with `mongodb.fields.auto.E001`.
  `config/mongo_apps.py` subclasses those AppConfigs. **The custom User model in Phase 2
  must do the same** on the `accounts` AppConfig.
- **Django's own contrib migrations are unusable as shipped.** They hardcode `AutoField`,
  and `post_migrate` rebuilds those models from the migration files rather than from the
  AppConfig — so `migrate` fails with *"Model instances without primary key value are
  unhashable"* while creating permissions. `MIGRATION_MODULES` points `admin`, `auth`, and
  `contenttypes` at regenerated copies in `mongo_migrations/`. Do not delete that package.
- **`ForeignKey` works but is slow** (compiles to `$lookup`), and **`prefetch_related` is
  unsupported**. Use `ForeignKey` only when the related object is genuinely independent.
- **`ManyToManyField` works, but avoid it anyway.** (Corrected in Phase 0 — earlier
  versions did not support it; 6.1 creates the implicit through-collection.) It still costs
  a `$lookup` per traversal and `prefetch_related` can't help. Model many-to-many as an
  `ArrayField` of `ObjectIdField`, or as an explicit through-model when the relationship
  carries data. Reach for a real `ManyToManyField` only with a reason in the PR.
- **Prefer embedding.** Data that is always read together with its parent should be an
  `EmbeddedModelField` / `EmbeddedModelArrayField`, not a separate collection. Comments live
  embedded inside their Post for exactly this reason.
- **Embedded-model migrations are only partly automatic.** 6.1 ships its own
  `MigrationAutodetector` (which is why `django_mongodb_backend` must stay in
  `INSTALLED_APPS`) and it does order embedded models correctly. Phase 1 measured the rest:
  adding a field to an embedded model **is** detected and does generate an `AddField` that
  applies cleanly — but **existing documents are not rewritten**. Reads of an old document
  return `None` for the new field, and ordering on it runs without error and produces
  silently meaningless results. Nothing warns you. Changing an embedded model's shape means
  a hand-written backfill (a reseed counts) — say so in the PR. Updating an embedded
  model's *indexes* after the collection exists is still unsupported outright.
- **Aggregation is limited** and `QuerySet.raw()` is unsupported. Use `raw_aggregate()` when
  you truly need a pipeline — but prefer our denormalized summary fields (below).
- **Denormalize rating averages.** `Course.rating_summary` and `Professor.rating_summary`
  store the averages and counts, recomputed whenever a rating is created, updated, or
  deleted. Never compute them with a live aggregation on a list page.
- **Transactions** require an Atlas replica set, have no savepoints, and cannot span DDL.
  Keep write paths simple rather than leaning on nested atomic blocks.
- **Unique constraints and indexes are supported** — use `UniqueConstraint` freely (one
  rating per user+course, one vote per user+target).
- **`.distinct()` needs an explicit `order_by()` on the same field.** A model's
  `Meta.ordering` is folded into the DISTINCT grouping, so
  `Course.objects.values_list("department").distinct()` dedupes on
  (code, department) and returns one row per course — 66 "departments" instead of 8, with
  no error. Always `.order_by(field)` first. This is the quietest bug we have hit: it
  returns wrong data rather than failing.
- **Rating sorts must pass `nulls_last=True`.** Unrated records hold null averages, and
  ascending order puts them first — so "easiest courses" would lead with the ones nobody
  has rated. `F("rating_summary__avg_difficulty").asc(nulls_last=True)` is supported and
  is the fix.
- **There is no `parse_uri()` any more.** It was removed in 6.1, but nearly every tutorial
  (and most LLM output) still calls it. Pass the whole Atlas connection string as the
  database `HOST` and set `NAME` separately. Read both from the environment.

## Commands

```bash
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py seed_demo          # load demo data (idempotent) — arrives in Phase 1
python manage.py createsuperuser
pytest                              # tests
ruff check . && ruff format --check .
npm run tailwind:watch              # rebuild CSS while you edit templates
```

Run `ruff check . && pytest` before declaring any work done.

## Project layout

```
config/                 # settings, urls, wsgi/asgi
  settings/base.py, dev.py, prod.py
apps/
  accounts/             # custom user, auth, profiles
  catalog/              # Course, Professor + directories
  ratings/              # CourseRating, ProfessorRating, summary recomputation
  community/            # Post, embedded Comment, Vote, tags, feed
  campus/               # Club, Job, ParkingLot, Facility
  saved/                # Collection, SavedItem (the filing cabinet)
  assistant/            # RAG index + the mascot assistant
  moderation/           # Report, ModAction, moderator queue
templates/              # base.html, partials/, per-app template dirs
static/                 # css, js, images
```

Each app holds `models.py`, `views.py`, `urls.py`, `forms.py`, `serializers.py` (DRF),
`services.py` (business logic), `admin.py`, and `tests/`.

## Conventions

- **Business logic lives in `services.py`**, not in views, templates, or serializers. Views
  parse the request, call a service, and render.
- **Templates render pages; DRF serves JSON.** A page is a Django template view. An
  interaction that updates part of a page is either an HTMX partial (returning HTML) or a
  DRF endpoint (returning JSON) — pick one per feature and be consistent.
- **Every view and endpoint checks authentication and authorization.** Never trust an id
  from the request; verify the object belongs to the requesting user before mutating.
  Use `LoginRequiredMixin` / `permission_classes`, plus explicit ownership checks.
- **Validate with Django forms or DRF serializers** at every boundary. No manual
  `request.POST[...]` parsing.
- Type-hint function signatures. Keep modules under ~300 lines.
- **Soft-delete user content** (`is_removed` flag) so thread structure survives.
- Django templates: keep logic out of them. Use template partials in
  `templates/partials/` for anything rendered in more than one place.

## Design direction

This is a student-facing product that has to look good enough that people want to use it.

- **Density over airiness.** This is a reference tool. Directory rows, ratings, and threads
  should be scannable — closer to Linear or GitHub than to a marketing landing page.
- **One accent color** derived from Farmingdale's green, used for actions and emphasis
  only. A neutral gray scale carries everything else.
- **Type:** one sans-serif family, three or four sizes total, generous line-height on body
  text (advice posts are read, not skimmed).
- **Ratings are the visual anchor** on directory rows and detail headers. Make them
  instantly legible — a number plus a compact bar or dot scale, never five-star clip art.
- Real loading states (HTMX indicators), real empty states with a call to action, real
  error states. Never a bare spinner on a blank page.
- **Mobile browser is a first-class target.** Test every screen at 375px.
- **Accessibility:** keyboard navigable, visible focus rings, labeled form controls, AA
  contrast. Run axe before calling a feature done.
- **The landing page (`/`) is the deliberate exception** to density: fullscreen, cinematic,
  slow motion. That exception stops at the front door — it never extends to the directories,
  detail pages, or anything a student uses to look something up.
- **Avoid the generic template look:** no purple-to-blue gradient heroes, no giant centered
  hero text on interior pages, no emoji used as iconography.

## Data model

Written as Django models. `ObjectIdAutoField` primary keys throughout. `Emb` = embedded.

```
User(AbstractUser)
  email(unique, college domain), display_name, major, grad_year, bio, avatar,
  role, is_profile_public
  courses_taken: EmbeddedModelArrayField(CourseTaken{course_id, semester})

Course
  code(unique, indexed), title, description, department, subject
  credits(nullable)                                 # 23 real catalog entries
                                                    # publish none; never guess
  prereq_text, coreq_text, catalog_year             # imported facts
  professor_ids: ArrayField(ObjectIdField)          # M2M replacement
  rating_summary: Emb(avg_difficulty, avg_workload, avg_usefulness, count)  # denormalized

Professor
  slug(unique, indexed)                             # directory key; also the URL
  first_name, last_name, department, title, photo, bio
  faculty_id, profile_url, department_url, phone, office, directory_retrieved
                                                    # imported facts, never edited in-app
  course_ids: ArrayField(ObjectIdField)
  rmp_legacy_id, rmp_avg_rating, rmp_avg_difficulty,
  rmp_would_take_again_pct, rmp_num_ratings, rmp_retrieved
                                                    # RateMyProfessors; source of truth
  rating_summary: Emb(avg_clarity, avg_helpfulness, avg_fairness,
                      avg_overall, count, source, rank_score)
                                                    # source: "ramhub" | "rmp" — never blank
                                                    # when count > 0
                                                    # rank_score: Bayesian, for sorting only

CourseRating      FK user, FK course, difficulty, workload, usefulness, semester
                  UniqueConstraint(user, course)
ProfessorRating   FK user, FK professor, clarity, helpfulness, fairness,
                  course_id?, semester
                  UniqueConstraint(user, professor)

Post
  FK author, kind, title, body, image_urls: ArrayField, tags: ArrayField(str)
  entity link — exactly one of: FK course? / professor? / club? / job?
  comments: EmbeddedModelArrayField(Comment)        # EMBEDDED, not a collection
  score, helpful_count                              # denormalized counters
  created_at, edited_at, is_removed
Comment (embedded)
  id: ObjectIdField, author_id, parent_id?, body, created_at, is_removed, score

Vote          FK user, target_type, target_id, value
              UniqueConstraint(user, target_type, target_id)
HelpfulMark   FK user, FK post — UniqueConstraint(user, post)

Club          name, description, category, meeting_info, contact_email, links: ArrayField
Job           title, employer, type, description, pay_info, link,
              FK posted_by?, expires_at
ParkingLot    name, permit_types: ArrayField, location, rules_text, tips
Facility      name, building_code, category, hours, amenities: ArrayField, location, notes

Collection    FK owner, name                        # filing-cabinet folder
SavedItem     FK user, FK collection?, target_type, target_id, created_at

Report        FK reporter, target_type, target_id, reason, note, status, FK handled_by?
ModAction     FK actor, target_type, target_id, action, note, created_at
Notification  FK user, type, payload: JSONField, read_at, created_at

DocChunk      source_type, source_id, url, text, embedding: ArrayField(FloatField)
              # indexed with MongoDB Atlas Vector Search
```

## Scope discipline

**Must-have (the mid-semester milestone):** auth and profiles · the Courses directory · the
Professors directory · course and professor detail pages with ratings and advice threads ·
the community feed with posts, comments, votes, and tags · global search · the filing
cabinet.

**Then, if on schedule:** campus-info tabs (clubs, jobs, parking, facilities) · the mascot
AI assistant with cited sources · filing-cabinet folders · the moderator queue · search
filters.

**Explicitly out of scope unless asked:** direct messaging · reputation and badges · dark
mode · a native mobile app · real-time/websocket anything · section-level (CRN) data.

**Do not build ahead.** If the current task doesn't ask for it, don't add it. Flag the idea
instead and let us decide.

## Definition of done

A feature is done when it:

- works on mobile (375px) and desktop
- is keyboard accessible with visible focus states
- has loading, empty, and error states
- enforces authorization server-side
- validates input through a Django form or DRF serializer
- has at least one pytest test covering its non-trivial logic
- passes `ruff check . && pytest`
