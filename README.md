# RamHub

A private, school-email-only community website for students of **Farmingdale State
College**. Look up any course or professor, read honest advice from students who
actually took it, and add your own.

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

# 6. Load demo courses, so the Courses directory is not empty
python manage.py seed_demo

# 7. Import the real faculty from the college directory
python manage.py import_directory
```

Both are idempotent — run them as often as you like.

`seed_demo` loads ~66 **demo** courses from
`apps/catalog/seed_data/demo_catalog.json`. Read the `_meta` block in that file
first: the courses only *resemble* the real Farmingdale catalog and are not
authoritative. Replace them when real catalog data is available.

`import_directory` loads the ~913 **real** teaching staff from
`apps/catalog/seed_data/farmingdale_directory.ndjson`, a public export of
[the campus directory](https://www.farmingdale.edu/directory/). Two rules it
will not bend:

- **It never writes ratings.** These are real, named people. Everyone starts at
  zero, and a re-import leaves any ratings students have left completely alone.
- **It never invents relationships.** The directory says who works here, not who
  teaches what, so it does not link professors to courses. Guessing would put a
  real person's name on a course they may never have taught.

Use `--prune --yes` to drop records that are no longer in the export (departed
staff, or leftover demo rows).

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

Then open <http://localhost:8000>. The design system lives at
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
