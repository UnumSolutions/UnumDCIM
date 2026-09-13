from django.db import migrations
from platform_core.migrations._tenant_rls_v1 import enable, disable


TABLES = ('registry_plugingrant',)


def protect(apps, schema_editor):
    enable(schema_editor, TABLES)


def unprotect(apps, schema_editor):
    disable(schema_editor, TABLES)


class Migration(migrations.Migration):
    dependencies = [("registry", "0001_initial"), ("platform_core", "0002_tenant_scope")]
    operations = [migrations.RunPython(protect, unprotect)]
