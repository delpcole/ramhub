"""
MongoDB-compatible AppConfigs for Django's built-in contrib apps.

Django's contrib apps pin ``default_auto_field = AutoField``, which overrides
the project-wide ``DEFAULT_AUTO_FIELD`` setting. MongoDB has no AutoField, so
without these subclasses ``manage.py check`` fails with
``mongodb.fields.auto.E001`` for auth.User, auth.Group, auth.Permission,
admin.LogEntry, and contenttypes.ContentType.

INSTALLED_APPS points at these classes instead of the stock apps.
"""

from django.contrib.admin.apps import AdminConfig
from django.contrib.auth.apps import AuthConfig
from django.contrib.contenttypes.apps import ContentTypesConfig

OBJECT_ID_AUTO_FIELD = "django_mongodb_backend.fields.ObjectIdAutoField"


class MongoAdminConfig(AdminConfig):
    default_auto_field = OBJECT_ID_AUTO_FIELD


class MongoAuthConfig(AuthConfig):
    default_auto_field = OBJECT_ID_AUTO_FIELD


class MongoContentTypesConfig(ContentTypesConfig):
    default_auto_field = OBJECT_ID_AUTO_FIELD
