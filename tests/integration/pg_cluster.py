"""Disposable PostgreSQL databases; never use ambient production PG variables."""
import secrets
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict


class Databases:
    def __init__(self, dsn):
        self.admin = psycopg.connect(dsn, autocommit=True)
        self.connection = conninfo_to_dict(dsn)
        self.prefix = "unum_test_" + uuid.uuid4().hex[:12]
        self.created = []

    def create(self, service):
        name = f"{self.prefix}_{service}"
        owner, app = name + "_owner", name + "_app"
        passwords = {role: secrets.token_urlsafe(32) for role in (owner, app)}
        # Track generated names before issuing DDL: a failed creation or a lost
        # response may still leave earlier roles or the database behind.
        self.created.append((name, owner, app))
        for role in (owner, app):
            self.admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(passwords[role])))
        self.admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(name), sql.Identifier(owner)))
        common = {"PGHOST": self.connection.get("host", "127.0.0.1"),
            "PGPORT": self.connection.get("port", "5432"), "PGDATABASE": name,
            "PGSSLMODE": self.connection.get("sslmode", "disable")}
        return (common | {"PGUSER": owner, "PGPASSWORD": passwords[owner]},
                common | {"PGUSER": app, "PGPASSWORD": passwords[app]})

    def grant(self, owner_env, app_env):
        with psycopg.connect(host=owner_env["PGHOST"], port=owner_env["PGPORT"],
                dbname=owner_env["PGDATABASE"], user=owner_env["PGUSER"],
                password=owner_env["PGPASSWORD"], sslmode=owner_env["PGSSLMODE"]) as connection:
            role = sql.Identifier(app_env["PGUSER"])
            connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
            connection.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(role))
            connection.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(role))
            connection.execute(sql.SQL("REVOKE UPDATE, DELETE ON platform_core_auditentry FROM {}").format(role))

    def close(self):
        errors = []
        try:
            for name, owner, app in reversed(self.created):
                statements = [sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))]
                statements.extend(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role))
                                  for role in (app, owner))
                for statement in statements:
                    try:
                        self.admin.execute(statement)
                    except psycopg.Error as exc:
                        errors.append(exc)
        finally:
            self.admin.close()
        if errors:
            raise RuntimeError(f"Qualification cleanup failed for {len(errors)} resource(s)") from errors[0]
        self.created.clear()
