"""
MongoDB-compatible replacements for Django's built-in contrib migrations.

Django ships migrations for admin, auth, and contenttypes that hardcode
``AutoField`` primary keys. During ``post_migrate`` Django rebuilds those models
from the migration files rather than from the live model classes, so the
ObjectIdAutoField set in config/mongo_apps.py never applies there. MongoDB
cannot generate an AutoField value, so the rows come back with ``pk = None`` and
``create_permissions()`` dies with "Model instances without primary key value
are unhashable".

Pointing MIGRATION_MODULES at this package makes Django regenerate those
migrations against the real (ObjectId) field types.

Regenerate with: python manage.py makemigrations admin auth contenttypes
"""
