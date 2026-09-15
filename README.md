# RamHub

A private, school-email-only community website for students of **Farmingdale State
College**. Look up any course or professor, read honest advice from students who
actually took it, and add your own.

**Team 1, CSC 325:** Axel, Cole, Nick, Sara, Sinan, Shil. The original project proposal is in [docs/PROPOSAL.md](docs/PROPOSAL.md).

Read [CLAUDE.md](CLAUDE.md) before contributing — it holds the architecture
decisions, MongoDB constraints, and conventions this project is built on.

---

## Prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| Python | 3.12+ | Built and tested on 3.13 |
| Node.js | 20+ | Only used to build the Tailwind CSS |
| MongoDB Atlas | any free cluster | A replica set — required for transactions |

**Versions are locked together.** `django-mongodb-backend` X.Y.* only works with
Django X.Y.*. We are on Django 6.1.1 + django-mongodb-backend 6.1.0. Upgrade
them in the same pull request or not at all.

---

## First-time setup

```bash
# 1. Python environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Node packages (Tailwind only)
npm install

# 3. Environment variables
cp .env.example .env              # then edit .env — see the table below

# 4. Build the stylesheet once
npm run tailwind:build

# 5. Create the collections Django needs
python manage.py migrate

# 6. Load real courses and faculty (runs both imports below)
python manage.py seed_demo
```

Everything is idempotent — run it as often as you like. `seed_demo` is a
convenience wrapper; you can run either import on its own:

| command | source | records |
|---|---|---|
| `import_catalog` | published [2025–26 course catalog](https://www.farmingdale.edu/course-offerings/catalog_2025_2026.html) | ~1,785 courses |
| `import_directory` | public [campus directory](https://www.farmingdale.edu/directory/) | ~913 teaching staff |
| `import_rmp` | [RateMyProfessors](https://www.ratemyprofessors.com/school/14046) export | ratings for ~517 of them |

Both exports live in `apps/catalog/seed_data/` with a `.README.md` documenting
provenance and caveats. `scrape_catalog.py` regenerates the course export when a
new catalog year is published.

Two rules neither import will bend:

- **Courses are never rated by an import.** No course has a rating until a
  student leaves one.
- **Professor ratings come from RateMyProfessors for now**, by explicit decision.
  Every one is tagged `source="rmp"` and labelled as RMP data everywhere it is
  shown — do not strip that. A rating a student leaves on RamHub always wins:
  `import_rmp` never overwrites one. About 40% of faculty have no RMP match and
  correctly show no rating.
- **They never invent relationships.** A directory says who works here; a catalog
  says a course exists. Neither says who teaches what, so courses are not linked
  to professors. That needs real section/schedule data.

Use `--prune --yes` to drop records no longer in the exports.

### Database: local or Atlas

Either works — it is one line in `.env`. Local is faster to set up and works
offline; Atlas is what the team shares and what the assistant's vector search
will need later.

**Local (macOS, Homebrew):**

```bash
brew tap mongodb/brew && brew trust mongodb/brew
brew install mongodb-community
```

MongoDB only supports transactions on a replica set, and Atlas is always one, so
run local as a single-node replica set to keep behaviour identical. Add this to
`/opt/homebrew/etc/mongod.conf`:

```yaml
replication:
  replSetName: rs0
```

Then start it and initiate the set once:

```bash
brew services start mongodb-community
mongosh --eval "rs.initiate()"
```

`.env`:

```
MONGODB_URI=mongodb://127.0.0.1:27017/?replicaSet=rs0
MONGODB_NAME=ramhub
```

Handy: `brew services stop mongodb-community`, and `mongosh ramhub` for a shell.

### Environment variables

`.env` is gitignored. Never commit it, and never put a connection string in a
settings file.

| Variable | Required | What it is |
| --- | --- | --- |
| `SECRET_KEY` | prod | Django signing key. Dev falls back to an insecure default. |
| `DEBUG` | no | `True` locally, `False` everywhere else. |
| `ALLOWED_HOSTS` | prod | Comma-separated hostnames. |
| `MONGODB_URI` | **yes** | The full Atlas connection string. |
| `MONGODB_NAME` | no | Database name inside the cluster. Defaults to `ramhub`. |
| `COLLEGE_EMAIL_DOMAIN` | no | Domain allowed to register. Defaults to `farmingdale.edu`. |

Generate a key for `.env` with:

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

**Atlas:**

1. In Atlas, create a free **M0** cluster.
2. **Database Access** → add a database user with a password.
3. **Network Access** → add your IP (or `0.0.0.0/0` while developing).
4. **Connect → Drivers → Python** → copy the connection string.
5. Paste it into `.env` as `MONGODB_URI`, replacing `<password>` with the real
   password. URL-encode any special characters in it.

```
MONGODB_URI=mongodb+srv://ramhub:REALPASSWORD@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
MONGODB_NAME=ramhub
```

The whole URI is passed straight through as the database `HOST`. Older
`django-mongodb-backend` tutorials call a `parse_uri()` helper — it no longer
exists in 6.1. Do not add it back.

---

## Running it

Two terminals:

```bash
# Terminal 1 — the site
source venv/bin/activate
python manage.py runserver
```

```bash
# Terminal 2 — rebuild CSS as you edit templates
npm run tailwind:watch
```

Then open <http://localhost:8000>. The front door is a cinematic landing page
(GSAP + ScrollTrigger + Lenis, vendored, loaded on that page only); the feed moved
to `/feed/`. The design system lives at
<http://localhost:8000/styleguide>.

If a class you added has no effect, the Tailwind watcher is not running.

---

## Checks

Both must pass before you open a pull request. CI runs them on every PR.

```bash
ruff check . && ruff format --check .
pytest
```

### Tests and the database

The tests run against a **real MongoDB**, in a separate database — pytest-django
creates and drops `test_<MONGODB_NAME>`, so your development data is never
touched. Your local MongoDB has to be running for `pytest` to work.

Any test that reads or writes needs `@pytest.mark.django_db`. That now includes
view tests for pages that only display things: the Courses and Professors pages
query on every request. The plain mark is enough — you do not need
`transaction=True` just because this is MongoDB. `conftest.py` explains why,
and what depends on MongoDB running as a replica set.

Useful extras:

```bash
python manage.py check          # Django system checks
ruff format .                   # apply formatting
python manage.py createsuperuser
```

---

## Layout

```
config/              settings/{base,dev,prod}.py, urls, views for site-level pages
  mongo_apps.py      MongoDB-compatible AppConfigs for Django's contrib apps
mongo_migrations/    regenerated admin/auth/contenttypes migrations (see its docstring)
  context_processors.py  builds the nav and marks the active tab
apps/                accounts, catalog, ratings, community, campus, saved,
                     assistant, moderation
apps/catalog/        Course + Professor, the two directories, and the detail
  services.py        pages. Query logic lives here, never in a view.
  forms.py           query-string validation for the directories
  seed_data/         demo_catalog.json — see its _meta block

templates/           base.html, partials/, one directory per app
static/src/          input.css — every design token lives here
static/css/          built output (gitignored)
static/vendor/       htmx
tests/               project-level tests; per-app tests live in apps/*/tests/
```

Per CLAUDE.md, each app grows `views.py`, `urls.py`, `forms.py`,
`serializers.py`, `services.py`, `admin.py`, and `tests/` as it needs them.
Business logic goes in `services.py`, never in a view or a template.

---

## The design system

All tokens are defined in [`static/src/input.css`](static/src/input.css) and
rendered on `/styleguide`. **Never hardcode a color, size, or radius in a
template** — the default Tailwind color and type scales are deliberately cleared,
so if a utility does not exist, add the token first.

Shared patterns: `.btn-primary` `.btn-secondary` `.btn-ghost` `.btn-danger`,
`.field-input` `.field-input-error` `.field-label` `.field-hint` `.field-error`,
`.card` `.card-pad` `.row-link`, `.badge-neutral` `.badge-accent` `.badge-danger`,
`.rating-value`.

Reusable partials: `partials/page_header.html`, `partials/empty_state.html`,
and the icon set in `partials/icons/`.

---

## HTMX

htmx 2.0.10 is vendored at `static/vendor/htmx.min.js`. `base.html` sets
`hx-headers` with Django's CSRF token on `<body>`, so POSTs work without any
per-form wiring.

An HTMX endpoint returns an **HTML fragment**, not JSON — see
`config.views.styleguide_htmx_demo` and `partials/htmx_demo_result.html` for the
pattern. JSON belongs in a DRF endpoint under `/api/`. Pick one per feature.
