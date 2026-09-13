"""Bounded, GET-only inspection of explicitly configured Nlyte read surfaces.

No vendor routes, field names, authentication behavior, or completeness rules are
inferred. Reports contain aggregate evidence only; no records or baseline writes.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import math
import re
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from uuid import uuid4

import httpx


class DiscoveryError(ValueError):
    """Safe error code, never include response data, URLs, or credentials."""


_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
_PATH = re.compile(r"/[A-Za-z0-9/_.~!$&'()*+,;=:@-]*\Z")
_MISSING = object()


def _fail(code):
    raise DiscoveryError(code)


def _keys(data, required, optional=()):
    if not isinstance(data, dict) or not set(required) <= data.keys() or set(data) - set(required) - set(optional):
        _fail("invalid_configuration")


def _number(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        _fail("invalid_limit")
    return value


def _integer(value, low, high):
    if type(value) is not int:
        _fail("invalid_limit")
    return _number(value, low, high)


def _pointer(value):
    if not isinstance(value, str) or len(value) > 512 or (value and not value.startswith("/")):
        _fail("invalid_field_pointer")
    if re.search(r"~(?![01])", value):
        _fail("invalid_field_pointer")
    return value


def _at(document, pointer):
    value = document
    if not pointer:
        return value
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or part not in value:
            return _MISSING
        value = value[part]
    return value


def _path(value):
    if (not isinstance(value, str) or not _PATH.fullmatch(value) or
            "//" in value or any(part in (".", "..") for part in value.split("/"))):
        _fail("invalid_allowed_path")
    return value


@dataclass(frozen=True)
class Collection:
    name: str
    path: str
    allowed_paths: tuple
    allowed_query_parameters: tuple
    page_size_parameter: str
    page_size: int
    items_path: str
    identity_path: str
    revision_path: str
    fields: dict
    next_path: str
    missing_next_is_terminal: bool
    completion_kind: str
    completion_path: str


@dataclass(frozen=True)
class DiscoveryConfig:
    origin: str
    authorization_scheme: str
    token_env: str
    timeout_seconds: float
    max_duration_seconds: float
    max_pages: int
    max_page_bytes: int
    max_records: int
    collections: tuple

    @classmethod
    def from_dict(cls, data):
        _keys(data, {"origin", "auth", "limits", "collections"}, {"allow_http_loopback"})
        if not isinstance(data["origin"], str) or any(c.isspace() or ord(c) < 32 for c in data["origin"]):
            _fail("invalid_origin")
        try:
            origin = urlsplit(data["origin"])
            port = origin.port
        except ValueError:
            _fail("invalid_origin")
        if (not origin.hostname or origin.username or origin.password or origin.query or origin.fragment or
                origin.path not in ("", "/") or "\\" in data["origin"]):
            _fail("invalid_origin")
        local = origin.hostname == "localhost"
        try:
            local |= ipaddress.ip_address(origin.hostname).is_loopback
        except ValueError:
            pass
        if origin.scheme != "https" and not (origin.scheme == "http" and local and data.get("allow_http_loopback") is True):
            _fail("https_required")
        # Canonicalize the origin once; default-port equivalence is accepted.
        host = f"[{origin.hostname}]" if ":" in origin.hostname else origin.hostname
        if port and port != (443 if origin.scheme == "https" else 80):
            host += f":{port}"
        base = f"{origin.scheme}://{host}"
        auth = data["auth"]
        _keys(auth, {"scheme", "token_env"})
        if auth["scheme"] not in ("Bearer", "Basic") or not isinstance(auth["token_env"], str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,99}", auth["token_env"]):
            _fail("invalid_auth_configuration")
        limits = data["limits"]
        _keys(limits, {"timeout_seconds", "max_duration_seconds", "max_pages", "max_page_bytes", "max_records"})
        timeout = _number(limits["timeout_seconds"], .1, 30)
        duration = _number(limits["max_duration_seconds"], .1, 300)
        max_pages = _integer(limits["max_pages"], 1, 100)
        max_bytes = _integer(limits["max_page_bytes"], 1, 2_000_000)
        max_records = _integer(limits["max_records"], 1, 100_000)
        if not isinstance(data["collections"], list) or not 1 <= len(data["collections"]) <= 20:
            _fail("invalid_collections")
        collections = []
        names = set()
        for raw in data["collections"]:
            _keys(raw, {"name", "path", "allowed_paths", "allowed_query_parameters", "page_size_parameter",
                        "page_size", "items_path", "identity_path", "revision_path", "fields", "next_path",
                        "missing_next_is_terminal", "completion"})
            if not isinstance(raw["name"], str) or not _IDENTIFIER.fullmatch(raw["name"]) or raw["name"] in names:
                _fail("invalid_collection_name")
            names.add(raw["name"])
            if not isinstance(raw["allowed_paths"], list) or not 1 <= len(raw["allowed_paths"]) <= 20:
                _fail("invalid_allowed_path")
            paths = tuple(_path(path) for path in raw["allowed_paths"])
            if _path(raw["path"]) not in paths:
                _fail("initial_path_not_allowed")
            parameters = raw["allowed_query_parameters"]
            if (not isinstance(parameters, list) or not 1 <= len(parameters) <= 20 or
                    any(not isinstance(p, str) or not re.fullmatch(r"[$A-Za-z_][$A-Za-z0-9_.-]{0,63}", p) for p in parameters) or
                    raw["page_size_parameter"] not in parameters):
                _fail("invalid_query_allowlist")
            fields = raw["fields"]
            if not isinstance(fields, dict) or not 1 <= len(fields) <= 100:
                _fail("invalid_field_mapping")
            for alias, pointer in fields.items():
                if not isinstance(alias, str) or not _IDENTIFIER.fullmatch(alias):
                    _fail("invalid_field_alias")
                _pointer(pointer)
            completion = raw["completion"]
            _keys(completion, {"kind", "path"})
            if completion["kind"] not in ("total_count", "terminal_flag"):
                _fail("invalid_completeness_rule")
            if type(raw["missing_next_is_terminal"]) is not bool:
                _fail("invalid_completeness_rule")
            collections.append(Collection(
                raw["name"], raw["path"], paths, tuple(parameters), raw["page_size_parameter"],
                _integer(raw["page_size"], 1, 500), _pointer(raw["items_path"]), _pointer(raw["identity_path"]),
                _pointer(raw["revision_path"]), dict(fields), _pointer(raw["next_path"]),
                raw["missing_next_is_terminal"], completion["kind"], _pointer(completion["path"])))
        return cls(base, auth["scheme"], auth["token_env"], timeout, duration, max_pages, max_bytes, max_records, tuple(collections))


def _origin(parts):
    try:
        return parts.scheme, parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        _fail("invalid_pagination_url")


def _request_url(config, collection, link, current=None):
    if not isinstance(link, str) or not link or len(link) > 8192 or any(ord(c) < 32 for c in link) or "\\" in link:
        _fail("invalid_pagination_url")
    try:
        parts = urlsplit(urljoin(current or config.origin + "/", link))
    except ValueError:
        _fail("invalid_pagination_url")
    if parts.username or parts.password or parts.fragment or _origin(parts) != _origin(urlsplit(config.origin)):
        _fail("pagination_origin_rejected")
    if parts.path not in collection.allowed_paths:
        _fail("pagination_path_rejected")
    try:
        query = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True, max_num_fields=20)
    except ValueError:
        _fail("invalid_pagination_query")
    if len({key for key, _ in query}) != len(query) or any(key not in collection.allowed_query_parameters for key, _ in query):
        _fail("pagination_query_rejected")
    size = dict(query).get(collection.page_size_parameter)
    if size is not None and (not size.isascii() or not size.isdigit() or not 1 <= int(size) <= collection.page_size):
        _fail("pagination_size_rejected")
    if size is None:
        query.append((collection.page_size_parameter, str(collection.page_size)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(sorted(query)), ""))


def _json_float(value):
    number = float(value)
    if not math.isfinite(number):
        _fail("invalid_json")
    return number


def _kind(value):
    if value is None:
        return "null"
    return {str: "string", bool: "boolean", int: "integer", float: "number", list: "array", dict: "object"}.get(type(value), "unsupported")


def fixture_transport(data):
    """Offline replay only. `sanitized` is the fixture author's attestation."""
    _keys(data, {"sanitized", "responses"})
    if data["sanitized"] is not True or not isinstance(data["responses"], list) or len(data["responses"]) > 2000:
        _fail("invalid_fixture")
    responses = {}
    for item in data["responses"]:
        _keys(item, {"request"}, {"status", "json", "text", "headers", "error"})
        if (not isinstance(item["request"], str) or not item["request"].startswith("/") or
                len(item["request"]) > 8192 or item["request"] in responses):
            _fail("invalid_fixture")
        if "error" in item:
            if set(item) != {"request", "error"} or item["error"] not in ("timeout", "unavailable"):
                _fail("invalid_fixture")
        else:
            if (("json" in item) == ("text" in item) or
                    "text" in item and not isinstance(item["text"], str) or
                    type(item.get("status", 200)) is not int or not 100 <= item.get("status", 200) <= 599):
                _fail("invalid_fixture")
            headers = item.get("headers", {})
            if (not isinstance(headers, dict) or len(headers) > 100 or
                    any(not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items())):
                _fail("invalid_fixture")
        responses[item["request"]] = item

    def handle(request):
        if request.method != "GET":
            _fail("write_method_forbidden")
        item = responses.get(request.url.raw_path.decode())
        if item is None:
            raise httpx.ConnectError("fixture_route_missing", request=request)
        if item.get("error") == "timeout":
            raise httpx.ReadTimeout("fixture_timeout", request=request)
        if item.get("error") == "unavailable":
            raise httpx.ConnectError("fixture_unavailable", request=request)
        kwargs = {"json": item["json"]} if "json" in item else {"text": item.get("text", "")}
        return httpx.Response(item.get("status", 200), headers=item.get("headers", {}), **kwargs)
    return httpx.MockTransport(handle)


def discover(config, *, token=None, transport=None, mode="live"):
    """Inspect configured reads; `complete` applies only to this source read.

    Neither complete nor incomplete discovery reports acknowledge peer agreement,
    create reconciliation snapshots, or advance any baseline.
    """
    if mode not in ("live", "fixture"):
        _fail("invalid_mode")
    if mode == "fixture" and transport is None:
        _fail("fixture_transport_required")
    if mode == "live" and (not isinstance(token, str) or not token.strip() or len(token) > 16_384 or any(ord(c) < 33 or ord(c) > 126 for c in token)):
        _fail("credential_missing_or_invalid")
    headers = {"Accept": "application/json", "User-Agent": "UnumDCIM-readonly-discovery/1"}
    if mode == "live":
        headers["Authorization"] = f"{config.authorization_scheme} {token}"
    report = {"contract": "unum.discovery/1", "mode": mode, "observation_id": str(uuid4()),
              "observed_at": datetime.now(timezone.utc).isoformat(), "complete": False,
              "writes_enabled": False, "baseline_advanced": False, "data_ready_for_reconciliation": False,
              "collections": []}
    deadline = time.monotonic() + config.max_duration_seconds
    with httpx.Client(headers=headers, follow_redirects=False, trust_env=False, transport=transport) as client:
        for collection in config.collections:
            result = {"name": collection.name, "complete": False, "pages_received": 0, "record_count": 0,
                      "field_types": {alias: [] for alias in collection.fields}, "odata_versions": [],
                      "session_max_age_seconds": [], "error": None}
            report["collections"].append(result)
            seen_urls, seen_ids, types = set(), set(), {alias: set() for alias in collection.fields}
            expected_count = None
            try:
                url = _request_url(config, collection, collection.path)
                for _ in range(config.max_pages):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        _fail("duration_limit")
                    if url in seen_urls:
                        _fail("pagination_cycle")
                    seen_urls.add(url)
                    with client.stream("GET", url, timeout=min(config.timeout_seconds, remaining)) as response:
                        if response.status_code != 200:
                            _fail(f"http_{response.status_code}")
                        content = bytearray()
                        for chunk in response.iter_bytes(chunk_size=65536):
                            if time.monotonic() >= deadline:
                                _fail("duration_limit")
                            if len(content) + len(chunk) > config.max_page_bytes:
                                _fail("page_bytes_limit")
                            content.extend(chunk)
                        version = response.headers.get("OData-Version", "")
                        if re.fullmatch(r"[0-9]{1,2}(?:\.[0-9]{1,2}){0,2}", version):
                            result["odata_versions"] = sorted(set(result["odata_versions"]) | {version})
                        for cookie in response.headers.get_list("Set-Cookie"):
                            match = re.search(r"(?:^|;)\s*max-age=([0-9]{1,10})(?:;|$)", cookie, re.I)
                            if match:
                                result["session_max_age_seconds"] = sorted(set(result["session_max_age_seconds"]) | {int(match[1])})
                    try:
                        document = json.loads(content, parse_float=_json_float, parse_constant=lambda _: _fail("invalid_json"))
                    except (ValueError, UnicodeError, RecursionError):
                        _fail("invalid_json")
                    items = _at(document, collection.items_path)
                    if not isinstance(items, list):
                        _fail("items_missing_or_invalid")
                    if len(items) > collection.page_size:
                        _fail("page_size_limit")
                    if result["record_count"] + len(items) > config.max_records:
                        _fail("record_limit")
                    marker = _at(document, collection.completion_path)
                    if collection.completion_kind == "total_count":
                        if type(marker) is not int or marker < 0:
                            _fail("completeness_marker_missing_or_invalid")
                        if expected_count is not None and expected_count != marker:
                            _fail("collection_changed_during_read")
                        expected_count = marker
                    elif type(marker) is not bool:
                        _fail("completeness_marker_missing_or_invalid")
                    for item in items:
                        identity, revision = _at(item, collection.identity_path), _at(item, collection.revision_path)
                        if any(type(value) not in (str, int) or not str(value).strip() for value in (identity, revision)):
                            _fail("identity_or_revision_missing")
                        key = (type(identity).__name__, identity)
                        if key in seen_ids:
                            _fail("duplicate_identity")
                        seen_ids.add(key)
                        for alias, pointer in collection.fields.items():
                            value = _at(item, pointer)
                            if value is _MISSING:
                                _fail("mapped_field_missing")
                            types[alias].add(_kind(value))
                    result["pages_received"] += 1
                    result["record_count"] += len(items)
                    next_link = _at(document, collection.next_path)
                    if next_link is _MISSING:
                        if not collection.missing_next_is_terminal:
                            _fail("pagination_marker_missing")
                        next_link = None
                    if next_link is None:
                        if (collection.completion_kind == "total_count" and result["record_count"] != expected_count or
                                collection.completion_kind == "terminal_flag" and marker is not True):
                            _fail("incomplete_collection")
                        result["complete"] = True
                        break
                    if collection.completion_kind == "terminal_flag" and marker is not False:
                        _fail("conflicting_completeness_markers")
                    url = _request_url(config, collection, next_link, url)
                else:
                    _fail("page_limit")
            except DiscoveryError as exc:
                result["error"] = str(exc)
            except httpx.TimeoutException:
                result["error"] = "request_timeout"
            except httpx.HTTPError:
                result["error"] = "transport_error"
            except (ValueError, TypeError, RecursionError):
                result["error"] = "invalid_response"
            result["field_types"] = {alias: sorted(kinds) for alias, kinds in types.items()}
    report["complete"] = all(item["complete"] for item in report["collections"])
    return report
