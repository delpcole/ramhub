"""
Project-wide pytest configuration.

## How pytest-django behaves against django-mongodb-backend

Verified in Phase 1 against MongoDB 8.3.9, so nobody has to rediscover it:

* A separate test database really is created and used. Tests run against
  ``test_<MONGODB_NAME>`` (e.g. ``test_ramhub``), never your development data.
* **The plain ``@pytest.mark.django_db`` mark works.** Rows created in one test
  are gone by the next — the usual transaction-and-rollback isolation behaves
  as it does on SQL backends. You do *not* need ``transaction=True`` just
  because this is MongoDB.
* ``@pytest.mark.django_db(transaction=True)`` also works, and cleans up
  correctly. Reach for it only when a test genuinely needs committed data
  (say, something asserting on real transaction behaviour) — it truncates
  collections instead of rolling back and is slower.

The one caveat: rollback isolation depends on MongoDB transactions, which
require a replica set. Locally and on Atlas that is satisfied. A bare
standalone ``mongod`` has no transactions, and Django then quietly degrades
``TestCase`` to truncate-between-tests — still correct, just slower. This is why
CI starts its MongoDB service as a single-node replica set rather than a plain
one; see .github/workflows/ci.yml.

Any test that touches the database needs the mark. Note that this now includes
view tests for pages that only *read* — the catalog directories query on every
request.
"""
