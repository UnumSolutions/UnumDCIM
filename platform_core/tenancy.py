"""Authenticated tenant context for direct or session-pooled PostgreSQL connections.

This context does not open a transaction. Transaction-pooling proxies are not
supported: a request's session setting must stay on its database connection.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from django.db import DatabaseError, connections


_tenant = ContextVar("unum_tenant", default=None)


def current_tenant():
    return _tenant.get()


def _check_runtime_role(connection, *, refresh=False):
    if not refresh and getattr(connection, "_unum_checked_connection", None) is connection.connection:
        return
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_roles
                WHERE (rolsuper OR rolbypassrls)
                  AND pg_has_role(current_user, oid, 'MEMBER')
            ), EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid
                WHERE n.nspname = ANY(current_schemas(false))
                  AND c.relkind IN ('r', 'p') AND a.attname = 'tenant' AND NOT a.attisdropped
                  AND (pg_has_role(current_user, c.relowner, 'MEMBER')
                       OR has_table_privilege(current_user, c.oid, 'TRUNCATE'))
            ), EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid
                WHERE n.nspname = ANY(current_schemas(false))
                  AND c.relkind IN ('r', 'p') AND a.attname = 'tenant' AND NOT a.attisdropped
                  AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
            )
        """)
        elevated, owns_or_truncates, unprotected = cursor.fetchone()
    if elevated or owns_or_truncates:
        raise RuntimeError("Use a restricted PostgreSQL runtime role without superuser, BYPASSRLS, table ownership or TRUNCATE privileges")
    if unprotected:
        raise RuntimeError("Tenant tables require ENABLE and FORCE ROW LEVEL SECURITY before serving requests")
    connection._unum_checked_connection = connection.connection


def validate_runtime_database(*, using="default", refresh=False):
    """Check connectivity and the actual runtime role without selecting a tenant."""
    connection = connections[using]
    connection.ensure_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    if connection.vendor == "postgresql":
        _check_runtime_role(connection, refresh=refresh)


@contextmanager
def tenant_scope(tenant_id, *, using="default"):
    if not isinstance(tenant_id, str) or not tenant_id.strip() or len(tenant_id) > 100:
        raise ValueError("A valid authenticated tenant is required")
    previous = _tenant.get()
    if previous is not None and previous != tenant_id:
        raise ValueError("Cannot change tenant within an active tenant scope")
    connection = connections[using]
    token = _tenant.set(tenant_id)
    configured = False
    try:
        if connection.vendor == "postgresql":
            connection.ensure_connection()
            _check_runtime_role(connection)
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('unum.tenant', %s, false)", [tenant_id])
            configured = True
        yield
    finally:
        try:
            if configured:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT set_config('unum.tenant', %s, false)", [previous or ""])
                except DatabaseError:
                    # An aborted transaction or disconnected socket must never
                    # return a tenant-configured connection to the pool.
                    connection.close()
        finally:
            _tenant.reset(token)
