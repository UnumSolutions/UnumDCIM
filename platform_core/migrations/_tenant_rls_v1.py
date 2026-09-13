"""Frozen PostgreSQL policy implementation shared by the initial RLS migrations."""


def enable(schema_editor, tables):
    if schema_editor.connection.vendor != "postgresql":
        return
    for name in tables:
        table = schema_editor.quote_name(name)
        schema_editor.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        schema_editor.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        condition = "tenant = nullif(current_setting('unum.tenant', true), '')"
        schema_editor.execute(f"CREATE POLICY unum_tenant_guard ON {table} AS RESTRICTIVE "
                              f"USING ({condition}) WITH CHECK ({condition})")
        schema_editor.execute(f"CREATE POLICY unum_tenant_access ON {table} "
                              f"USING ({condition}) WITH CHECK ({condition})")


def disable(schema_editor, tables):
    if schema_editor.connection.vendor != "postgresql":
        return
    for name in tables:
        table = schema_editor.quote_name(name)
        schema_editor.execute(f"DROP POLICY unum_tenant_access ON {table}")
        schema_editor.execute(f"DROP POLICY unum_tenant_guard ON {table}")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
