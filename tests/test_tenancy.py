import pytest
from django.db import DatabaseError
from platform_core import tenancy


class Connection:
    vendor = "postgresql"

    def __init__(self, role_flags=(False, False, False)):
        self.connection = object()
        self.role_flags = role_flags
        self.settings = []
        self.role_checks = 0
        self.closed = False
        self.fail_reset = False

    def ensure_connection(self):
        pass

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=None):
        if params is None:
            self.role_checks += 1
        else:
            if self.fail_reset and params == [""]:
                raise DatabaseError("aborted transaction")
            self.settings.append(params[0])

    def fetchone(self):
        return self.role_flags

    def close(self):
        self.closed = True


@pytest.fixture
def connection(monkeypatch):
    connection = Connection()
    monkeypatch.setattr(tenancy, "connections", {"default": connection})
    return connection


def test_exception_resets_tenant_and_connection_setting(connection):
    with pytest.raises(RuntimeError, match="handler failed"):
        with tenancy.tenant_scope("tenant-a"):
            assert tenancy.current_tenant() == "tenant-a"
            raise RuntimeError("handler failed")
    assert tenancy.current_tenant() is None
    assert connection.settings == ["tenant-a", ""]


def test_nested_scopes_restore_tenant_and_reject_switches(connection):
    with tenancy.tenant_scope("tenant-a"):
        with tenancy.tenant_scope("tenant-a"):
            assert tenancy.current_tenant() == "tenant-a"
        with pytest.raises(ValueError, match="Cannot change tenant"):
            with tenancy.tenant_scope("tenant-b"):
                pytest.fail("Cross-tenant scope must not enter")
        assert tenancy.current_tenant() == "tenant-a"
    assert connection.settings == ["tenant-a", "tenant-a", "tenant-a", ""]


def test_failed_reset_closes_connection(connection):
    connection.fail_reset = True
    with tenancy.tenant_scope("tenant-a"):
        pass
    assert connection.closed
    assert tenancy.current_tenant() is None


@pytest.mark.parametrize("flags", [(True, False, False), (False, True, False), (False, False, True)])
def test_elevated_role_or_unprotected_tables_fail_closed(connection, flags):
    connection.role_flags = flags
    with pytest.raises(RuntimeError):
        with tenancy.tenant_scope("tenant-a"):
            pytest.fail("Unsafe database must not serve a tenant")
    assert connection.settings == []
    assert tenancy.current_tenant() is None


def test_runtime_validation_is_cached_per_physical_connection(connection):
    for tenant in ("tenant-a", "tenant-b"):
        with tenancy.tenant_scope(tenant):
            pass
    assert connection.role_checks == 1
    connection.connection = object()
    with tenancy.tenant_scope("tenant-c"):
        pass
    assert connection.role_checks == 2


@pytest.mark.parametrize("tenant", [None, "", " ", 1, "a" * 101])
def test_invalid_tenant_never_configures_a_connection(connection, tenant):
    with pytest.raises(ValueError):
        with tenancy.tenant_scope(tenant):
            pytest.fail("Invalid tenant must not enter")
    assert connection.settings == []


def test_sqlite_keeps_explicit_scope_without_postgresql_statements(connection):
    connection.vendor = "sqlite"
    with tenancy.tenant_scope("tenant-a"):
        assert tenancy.current_tenant() == "tenant-a"
    assert connection.settings == []
