import json
import subprocess

import psycopg
import pytest

from pg_cluster import Databases
import pg_cluster
from scripts import qualify


class Admin:
    def __init__(self, fail_create=False, fail_drop=False):
        self.statements = []
        self.fail_create = fail_create
        self.fail_drop = fail_drop
        self.closed = False

    def execute(self, statement):
        statement = statement.as_string()
        self.statements.append(statement)
        if self.fail_create and statement.startswith("CREATE ROLE") and len(self.statements) == 2:
            raise psycopg.OperationalError("second role creation failed")
        if self.fail_drop and statement.startswith("DROP DATABASE"):
            raise psycopg.OperationalError("database cleanup failed")

    def close(self):
        self.closed = True


def test_partial_database_creation_still_cleans_every_generated_name(monkeypatch):
    admin = Admin(fail_create=True)
    monkeypatch.setattr(pg_cluster.psycopg, "connect", lambda *args, **kwargs: admin)
    databases = Databases("host=127.0.0.1 dbname=postgres user=postgres")
    with pytest.raises(psycopg.OperationalError):
        databases.create("inventory")
    name, owner, app = databases.created[0]
    databases.close()
    assert any(statement.startswith("DROP DATABASE IF EXISTS") and name in statement for statement in admin.statements)
    assert all(any(statement.startswith("DROP ROLE IF EXISTS") and role in statement
                   for statement in admin.statements) for role in (owner, app))
    assert admin.closed


def test_database_cleanup_continues_after_one_drop_fails(monkeypatch):
    admin = Admin(fail_drop=True)
    monkeypatch.setattr(pg_cluster.psycopg, "connect", lambda *args, **kwargs: admin)
    databases = Databases("host=127.0.0.1 dbname=postgres user=postgres")
    databases.created = [("first", "first_owner", "first_app"), ("second", "second_owner", "second_app")]
    with pytest.raises(RuntimeError, match="2 resource"):
        databases.close()
    assert len(admin.statements) == 6
    assert admin.closed


class Port:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def bind(self, address):
        pass

    def getsockname(self):
        return "127.0.0.1", 45000


@pytest.fixture
def qualification(monkeypatch, tmp_path):
    monkeypatch.setattr(qualify, "ROOT", tmp_path)
    monkeypatch.setattr(qualify.sys, "argv", ["qualify.py"])
    monkeypatch.setattr(qualify.socket, "socket", Port)
    def docker(*args, **kwargs):
        if args[:2] == ("image", "inspect"):
            return json.dumps([{"RepoDigests": ["test@sha256:" + "a" * 64]}])
        if args[0] == "run":
            return args[args.index("--name") + 1]
        if args[0] == "port":
            return "127.0.0.1:45000"
        return ""
    monkeypatch.setattr(qualify, "docker", docker)
    return tmp_path, docker


def test_failed_docker_run_still_removes_named_container(monkeypatch, qualification):
    root, docker = qualification
    removed = []
    def fail_run(*args, **kwargs):
        if args[0] == "run":
            raise subprocess.CalledProcessError(1, ["docker", "run"])
        return docker(*args, **kwargs)
    def run(args, **kwargs):
        removed.append(args[-1])
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(qualify, "docker", fail_run)
    monkeypatch.setattr(qualify.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        qualify.main()
    assert len(removed) == 1 and removed[0].endswith("-postgres")
    assert json.loads((root / ".data/qualification/latest.json").read_text())["exit_code"] == 1


def test_failed_container_cleanup_marks_qualification_failed(monkeypatch, qualification):
    root, _ = qualification
    removed = []
    def run(args, **kwargs):
        if args[:2] == ["docker", "rm"]:
            removed.append(args[-1])
            return subprocess.CompletedProcess(args, 1 if len(removed) == 1 else 0, "", "daemon unavailable")
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(qualify.subprocess, "run", run)
    assert qualify.main() == 1
    assert len(removed) == 2
    evidence = json.loads((root / ".data/qualification/latest.json").read_text())
    assert evidence["exit_code"] == 1
    assert evidence["cleanup_failed"] == [removed[0]]
    assert "password=" not in json.dumps(evidence)
