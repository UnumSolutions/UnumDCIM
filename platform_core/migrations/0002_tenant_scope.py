from django.db import migrations, models
from platform_core.migrations._tenant_rls_v1 import enable, disable


TABLES = ("platform_core_outbox", "platform_core_inbox", "platform_core_audithead", "platform_core_auditentry")


def backfill_tenants(apps, schema_editor):
    alias = schema_editor.connection.alias
    Inbox = apps.get_model("platform_core", "Inbox")
    Entry = apps.get_model("platform_core", "AuditEntry")
    Head = apps.get_model("platform_core", "AuditHead")
    if Inbox.objects.using(alias).exists():
        raise RuntimeError("Legacy inbox records have no tenant provenance. Reconcile their tenant ownership before this migration; deduplication records cannot be assigned or discarded automatically.")
    for entry in Entry.objects.using(alias).iterator():
        tenant = entry.payload.get("tenant") if isinstance(entry.payload, dict) else None
        if (not isinstance(tenant, str) or not tenant.strip() or len(tenant) > 100
                or not entry.chain.startswith(tenant + "/")):
            raise RuntimeError("Audit entry has invalid tenant provenance: " + str(entry.pk))
        Entry.objects.using(alias).filter(pk=entry.pk).update(tenant=tenant)
    for head in Head.objects.using(alias).iterator():
        tenants = set(Entry.objects.using(alias).filter(chain=head.chain).values_list("tenant", flat=True))
        if not tenants and head.sequence == 0 and head.digest == "0" * 64:
            parts = head.chain.split("/")
            if len(parts) == 3 and all(parts) and len(parts[0]) <= 100:
                tenants.add(parts[0])
        if len(tenants) != 1:
            raise RuntimeError("Audit head has ambiguous tenant provenance: " + head.chain)
        Head.objects.using(alias).filter(pk=head.pk).update(tenant=tenants.pop())


def protect(apps, schema_editor):
    enable(schema_editor, TABLES)
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE FUNCTION unum_reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Audit entries are append-only' USING ERRCODE = '42501';
        END;
        $$
    """)
    schema_editor.execute("""
        CREATE TRIGGER unum_audit_append_only BEFORE UPDATE OR DELETE OR TRUNCATE
        ON platform_core_auditentry FOR EACH STATEMENT
        EXECUTE FUNCTION unum_reject_audit_mutation()
    """)
    schema_editor.execute("ALTER TABLE platform_core_auditentry ENABLE ALWAYS TRIGGER unum_audit_append_only")
    schema_editor.execute("REVOKE UPDATE, DELETE, TRUNCATE ON platform_core_auditentry FROM PUBLIC")


def unprotect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER unum_audit_append_only ON platform_core_auditentry")
        schema_editor.execute("DROP FUNCTION unum_reject_audit_mutation()")
    disable(schema_editor, TABLES)


class Migration(migrations.Migration):
    dependencies = [("platform_core", "0001_initial")]
    operations = [
        migrations.AddField("inbox", "tenant", models.CharField(max_length=100, null=True)),
        migrations.AddField("audithead", "tenant", models.CharField(max_length=100, null=True)),
        migrations.AddField("auditentry", "tenant", models.CharField(max_length=100, null=True)),
        migrations.RunPython(backfill_tenants, migrations.RunPython.noop),
        migrations.AlterField("inbox", "tenant", models.CharField(max_length=100)),
        migrations.AlterField("audithead", "tenant", models.CharField(max_length=100)),
        migrations.AlterField("auditentry", "tenant", models.CharField(max_length=100)),
        migrations.RunPython(protect, unprotect),
    ]
