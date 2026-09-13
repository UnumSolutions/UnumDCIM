"""Exercise real httpx GET/pagination paths with controlled local responses."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import httpx
import pytest

from unum_sync.discovery import DiscoveryConfig, DiscoveryError, discover, fixture_transport


ROOT = Path(__file__).resolve().parents[1]


def config_data():
    return json.loads((ROOT / "examples/nlyte-discovery.example.json").read_text())


def config(**limits):
    data = config_data()
    data["limits"].update(limits)
    return DiscoveryConfig.from_dict(data)


def record(identity="synthetic-1", **changes):
    return {"id": identity, "version": "1", "name": "Sensitive customer name", "rack": "Sensitive rack", **changes}


def page(items=None, next_link=None, total=1):
    return {"records": [record()] if items is None else items, "next": next_link, "total": total}


def run_pages(pages, discovery_config=None):
    requested = []
    iterator = iter(pages)

    def respond(request):
        requested.append(request)
        response = next(iterator)
        if isinstance(response, Exception):
            raise response
        return response if isinstance(response, httpx.Response) else httpx.Response(200, json=response)

    report = discover(discovery_config or config(), token="secret-credential", transport=httpx.MockTransport(respond))
    return report, requested


def test_complete_pagination_is_get_only_and_report_contains_no_credentials_or_records():
    report, requests = run_pages([
        httpx.Response(200, json=page(next_link="?cursor=opaque-private-cursor", total=2), headers={
            "OData-Version": "4.0", "Set-Cookie": "session=secret-cookie; Max-Age=1800; HttpOnly"}),
        page([record("synthetic-2")], total=2),
    ])
    assert report["complete"] is True
    assert report["baseline_advanced"] is False
    assert report["writes_enabled"] is False
    assert report["data_ready_for_reconciliation"] is False
    assert report["collections"][0] == {
        "name": "synthetic_assets", "complete": True, "pages_received": 2, "record_count": 2,
        "field_types": {"display_name": ["string"], "rack_reference": ["string"]},
        "odata_versions": ["4.0"], "session_max_age_seconds": [1800], "error": None,
    }
    assert [request.method for request in requests] == ["GET", "GET"]
    assert all(request.content == b"" for request in requests)
    assert all(request.headers["authorization"] == "Bearer secret-credential" for request in requests)
    assert str(requests[1].url).endswith("?cursor=opaque-private-cursor&limit=2")
    serialized = json.dumps(report)
    for private in ("secret-credential", "secret-cookie", "Sensitive", "synthetic-1", "opaque-private-cursor", "customer-approved-host"):
        assert private not in serialized


@pytest.mark.parametrize("link,code", [
    ("https://attacker.invalid/synthetic/assets?cursor=secret", "pagination_origin_rejected"),
    ("//attacker.invalid/synthetic/assets", "pagination_origin_rejected"),
    ("https://user:password@customer-approved-host.invalid/synthetic/assets", "pagination_origin_rejected"),
    ("/unapproved/delete", "pagination_path_rejected"),
    ("/synthetic/%61ssets", "pagination_path_rejected"),
    ("?unauthorized=private", "pagination_query_rejected"),
    ("?limit=500", "pagination_size_rejected"),
    ("?limit=2&limit=2", "pagination_query_rejected"),
    ("#private", "pagination_origin_rejected"),
    ("", "invalid_pagination_url"),
])
def test_rejects_unsafe_next_link_before_any_second_request(link, code):
    report, requests = run_pages([page(next_link=link, total=2)])
    assert len(requests) == 1
    assert report["complete"] is False
    assert report["collections"][0]["error"] == code
    assert "private" not in json.dumps(report)


def test_redirect_is_not_followed_even_when_same_origin():
    report, requests = run_pages([httpx.Response(302, headers={"Location": "/synthetic/assets?cursor=redirect"})])
    assert len(requests) == 1
    assert report["collections"][0]["error"] == "http_302"
    assert report["complete"] is False


@pytest.mark.parametrize("error", [
    httpx.ReadTimeout("Credential secret-credential at private URL"),
    httpx.ConnectError("Customer hostname and sensitive connection details"),
])
def test_failure_after_first_page_remains_partial_without_advancing_baseline(error):
    report, _ = run_pages([page(next_link="?cursor=2", total=2), error])
    result = report["collections"][0]
    assert result["record_count"] == 1
    assert result["pages_received"] == 1
    assert result["complete"] is False
    assert result["error"] in ("request_timeout", "transport_error")
    assert report["complete"] is False
    assert report["baseline_advanced"] is False
    assert "secret-credential" not in json.dumps(report)
    assert "Customer hostname" not in json.dumps(report)


@pytest.mark.parametrize("document,code", [
    ({"next": None, "total": 0}, "items_missing_or_invalid"),
    ({"records": [], "total": 0}, "pagination_marker_missing"),
    ({"records": [], "next": None}, "completeness_marker_missing_or_invalid"),
    (page(total=True), "completeness_marker_missing_or_invalid"),
    (page(total=2), "incomplete_collection"),
    (page([{"id": "a", "version": "1", "name": "name"}]), "mapped_field_missing"),
    (page([record(version="")]), "identity_or_revision_missing"),
    (page([record(id=None)]), "identity_or_revision_missing"),
    (page([record(), record(), record()], total=3), "page_size_limit"),
])
def test_incomplete_and_malformed_reads_are_never_complete(document, code):
    report, _ = run_pages([document])
    assert report["complete"] is False
    assert report["collections"][0]["error"] == code
    assert report["baseline_advanced"] is False


def test_count_change_and_duplicate_identity_prevent_completion():
    changed, _ = run_pages([page(next_link="?cursor=2", total=2), page([record("other")], total=3)])
    assert changed["collections"][0]["error"] == "collection_changed_during_read"
    duplicate, _ = run_pages([page(next_link="?cursor=2", total=2), page(total=2)])
    assert duplicate["collections"][0]["error"] == "duplicate_identity"
    assert duplicate["complete"] is False


@pytest.mark.parametrize("limits,first,code", [
    ({"max_pages": 1}, page(next_link="?cursor=2", total=2), "page_limit"),
    ({"max_records": 1}, page([record("one"), record("two")], total=2), "record_limit"),
    ({"max_page_bytes": 20}, page(), "page_bytes_limit"),
])
def test_explicit_limits_fail_closed(limits, first, code):
    report, requests = run_pages([first], config(**limits))
    assert len(requests) == 1
    assert report["collections"][0]["error"] == code
    assert report["complete"] is False


def test_pagination_cycle_is_detected_without_repeating_request():
    report, requests = run_pages([page(next_link="?limit=2", total=2)])
    assert len(requests) == 1
    assert report["collections"][0]["error"] == "pagination_cycle"


def test_duration_limit_is_enforced_during_transfer(monkeypatch):
    now = [0]
    monkeypatch.setattr("unum_sync.discovery.time.monotonic", lambda: now[0])

    def slow(_):
        now[0] = 31
        return httpx.Response(200, json=page())

    report = discover(config(), token="private", transport=httpx.MockTransport(slow))
    assert report["collections"][0]["error"] == "duration_limit"
    assert report["complete"] is False


def test_terminal_flag_and_explicit_missing_link_rule():
    raw = config_data()
    raw["collections"][0]["completion"] = {"kind": "terminal_flag", "path": "/done"}
    raw["collections"][0]["missing_next_is_terminal"] = True
    report, _ = run_pages([
        {**page(next_link="?cursor=2"), "done": False},
        {"records": [record("other")], "done": True},
    ], DiscoveryConfig.from_dict(raw))
    assert report["complete"] is True
    invalid, _ = run_pages([{**page(next_link="?cursor=2"), "done": True}], DiscoveryConfig.from_dict(raw))
    assert invalid["collections"][0]["error"] == "conflicting_completeness_markers"
    incomplete, _ = run_pages([{**page(), "done": False}], DiscoveryConfig.from_dict(raw))
    assert incomplete["collections"][0]["error"] == "incomplete_collection"


def test_all_collections_must_complete():
    raw = config_data()
    other = copy.deepcopy(raw["collections"][0])
    other["name"] = "other_collection"
    raw["collections"].append(other)
    report, _ = run_pages([page(), httpx.Response(503, text="Sensitive error body")], DiscoveryConfig.from_dict(raw))
    assert report["collections"][0]["complete"] is True
    assert report["collections"][1]["complete"] is False
    assert report["complete"] is False
    assert "Sensitive error body" not in json.dumps(report)


def test_untrusted_header_values_and_invalid_json_do_not_leak():
    report, _ = run_pages([httpx.Response(200, text="secret response body", headers={"OData-Version": "secret version value"})])
    assert report["collections"][0]["error"] == "invalid_json"
    assert "secret" not in json.dumps(report)


@pytest.mark.parametrize("origin", [
    "http://customer.invalid", "https://user:password@customer.invalid", "https://customer.invalid/path",
    "https://customer.invalid?token=private", "https://customer.invalid/#private", "https://customer.invalid:bad",
])
def test_live_origin_rejects_credentials_paths_and_plaintext(origin):
    raw = config_data()
    raw["origin"] = origin
    with pytest.raises(DiscoveryError):
        DiscoveryConfig.from_dict(raw)


def test_loopback_http_requires_explicit_opt_in():
    raw = config_data()
    raw["origin"] = "http://127.0.0.1:8999"
    with pytest.raises(DiscoveryError, match="https_required"):
        DiscoveryConfig.from_dict(raw)
    raw["allow_http_loopback"] = True
    assert DiscoveryConfig.from_dict(raw).origin == raw["origin"]


@pytest.mark.parametrize("credential", [None, "", " ", "secret\nInjected: header"])
def test_live_credentials_are_required_and_never_exposed_in_errors(credential):
    with pytest.raises(DiscoveryError, match="credential_missing_or_invalid"):
        discover(config(), token=credential)


def test_fixture_replay_never_uses_credentials_or_network(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: pytest.fail("Network connection attempted"))
    fixture = {"sanitized": True, "responses": [{"request": "/synthetic/assets?limit=2", "json": page()}]}
    report = discover(config(), token="must-not-be-used", transport=fixture_transport(fixture), mode="fixture")
    assert report["complete"] is True
    assert report["mode"] == "fixture"
    assert "must-not-be-used" not in json.dumps(report)
    with pytest.raises(DiscoveryError, match="fixture_transport_required"):
        discover(config(), mode="fixture")


def test_missing_fixture_route_is_partial_not_a_live_fallback():
    report = discover(config(), transport=fixture_transport({"sanitized": True, "responses": []}), mode="fixture")
    assert report["complete"] is False
    assert report["collections"][0]["error"] == "transport_error"


def test_cli_replay_writes_new_report_and_refuses_to_overwrite_existing_baseline(tmp_path):
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"sanitized": True, "responses": [{"request": "/synthetic/assets?limit=2", "json": page()}]}))
    output = tmp_path / "report.json"
    args = [sys.executable, str(ROOT / "scripts/discover_nlyte.py"), "--config",
            str(ROOT / "examples/nlyte-discovery.example.json"), "--fixture", str(fixture), "--output", str(output)]
    first = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
    assert first.returncode == 0, first.stderr
    original = output.read_bytes()
    assert json.loads(original)["baseline_advanced"] is False
    assert os.stat(output).st_mode & 0o777 == 0o600
    again = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
    assert again.returncode == 2
    assert json.loads(again.stderr)["error"] == "local_file_error"
    assert output.read_bytes() == original


@pytest.mark.parametrize("number", ["NaN", "Infinity", "1e999"])
def test_nonfinite_json_never_becomes_a_complete_observation(number):
    raw = '{"records":[{"id":"a","version":"1","name":' + number + ',"rack":"r"}],"next":null,"total":1}'
    report, _ = run_pages([httpx.Response(200, text=raw)])
    assert report["complete"] is False
    assert report["collections"][0]["error"] == "invalid_json"


@pytest.mark.parametrize("item", [
    {"request": "/read", "json": {}, "text": "private"},
    {"request": "/read", "json": {}, "headers": {"private": {"secret": "value"}}},
    {"request": "/read", "error": "unvalidated private exception"},
    {"request": "/read", "json": {}, "status": "private"},
])
def test_malformed_fixture_is_rejected_with_safe_error(item):
    with pytest.raises(DiscoveryError, match="invalid_fixture"):
        fixture_transport({"sanitized": True, "responses": [item]})
