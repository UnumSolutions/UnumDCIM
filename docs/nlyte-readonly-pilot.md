# Read-only Nlyte discovery pilot

The discovery harness is ready for configured read surfaces and sanitized fixture
replay. No customer Nlyte instance has been inspected. The example routes, token
scheme, and JSON fields are **synthetic placeholders**, not vendor API claims.
This work does not complete [D32](decisions/01-addendum-a.md#d32-nlyte-api-validation-gate-phase-0-exit-criterion)
or the [target-instance discovery checklist](nlyte-discovery-checklist.md).

The harness sends GET requests only. It never imports records, invokes workflows,
changes field ownership, writes to Nlyte, creates reconciliation snapshots, or
advances a baseline. The existing placement UI continues to show synthetic data.

## Configure an approved target

Keep the real configuration, credentials, customer responses, and discovery
reports outside this public repository. Obtain the licensed API contract and a
customer-approved read account before configuring live access. Copy
`examples/nlyte-discovery.example.json` to a private working directory and replace
all placeholders with evidence from that specific instance:

- `origin`: the HTTPS origin only, with no path, query, or embedded credentials.
- `auth`: the verified `Bearer` or `Basic` authorization scheme and an environment
  variable name containing its credential. For Basic, supply the already encoded
  credential string. No login endpoint, interactive SSO, or token refresh is
  inferred or called. Unsupported authentication needs a separately reviewed
  adapter.
- `path` and `allowed_paths`: exact verified GET paths. All pagination links must
  use this origin and one of these paths. Redirects are refused, including
  same-origin redirects; add the final approved read path to the configuration.
- `allowed_query_parameters`, `page_size_parameter`, and `page_size`: the verified
  query contract. The page size parameter is supplied on every request. Links
  requesting a larger page or unapproved query parameter are rejected.
- `items_path`, `identity_path`, `revision_path`, and `fields`: JSON pointers using
  `/` for nesting and `~0` / `~1` for literal `~` / `/`. Identity, revision, and
  every mapped field must be present on every record. Field aliases are local
  report labels; values never appear in a report. Pointers traverse object keys,
  not array indexes.
- `next_path`: a next-link pointer. A present JSON `null` means terminal. Missing
  next links are errors unless `missing_next_is_terminal` is explicitly true
  and that behavior was validated against the target.
- `completion`: either `total_count`, requiring a stable nonnegative total on
  every page and exactly that many distinct records at the end, or
  `terminal_flag`, requiring false on pages with a next link and true on the
  terminal page. Choose the rule only after testing the target's semantics.

Limits cap page bytes, records, pages, request timeouts, and total run duration.
A returned page larger than the requested size is a failure, even if the server
ignores its page-size parameter. Requests run serially. HTTP is accepted only for
explicitly enabled loopback testing (`allow_http_loopback: true`). Environment
proxies are ignored, TLS verification remains enabled, and automatic redirects
and retries are disabled.

Set the configured credential through your usual secret-delivery mechanism;
avoid putting it in command arguments, configuration files, or shell history.
Run the following from the repository root after the environment is prepared:

```sh
.venv/bin/python scripts/discover_nlyte.py \
  --config /private/path/nlyte-discovery.json \
  --output /private/path/new-read-report.json
```

The output path must be new. The command refuses to overwrite an existing report,
fixture, or baseline. Exit status is 0 for a complete configured read, 1 for an
incomplete read, and 2 for a local configuration, credential, or file error.

## Replay sanitized acceptance evidence

The replay format contains a `sanitized: true` assertion and explicit HTTP
responses indexed by the request path and canonical query string. The assertion
is supplied by the fixture author; the tool does not certify sanitization. Remove
customer data, credentials, session cookies, and restricted vendor material
before sharing a fixture. Prefer fully synthetic identifiers and values.

This fixture matches the checked-in synthetic example:

```json
{
  "sanitized": true,
  "responses": [
    {
      "request": "/synthetic/assets?limit=2",
      "status": 200,
      "headers": {"OData-Version": "4.0"},
      "json": {
        "records": [{"id": "demo-1", "version": "1", "name": "Demo server", "rack": "demo-rack"}],
        "next": null,
        "total": 1
      }
    }
  ]
}
```

Save it outside the repository and run:

```sh
.venv/bin/python scripts/discover_nlyte.py \
  --config examples/nlyte-discovery.example.json \
  --fixture /private/path/sanitized-read-fixture.json
```

Fixture mode never reads the credential environment variable or opens network
connections. It exercises the same route validation, parser, pagination, and
completeness checks as live mode. A fixture response can use `text` instead of
`json` for malformed responses or `error: "timeout"` to test interruption.

## Interpret evidence and finish acceptance

Reports include an observation ID and time, completion and error codes, page and
record counts, inferred JSON types for mapped aliases, numeric OData version
headers, and numeric cookie `Max-Age` values when present. They omit origins,
paths, query strings, credentials, raw records, response bodies, raw headers,
cookie contents, and transport error messages. Cookie age alone does not prove
session lifetime. HTTP error codes are recorded without vendor response text.

A partial read always has `complete: false`; its counts describe only records
in fully validated pages before the failure. Missing fields, pagination loops,
redirects, count changes, duplicate identities, limit exhaustion, malformed
responses, and outages all prevent completion. A failed collection prevents the
whole report from being complete. No incomplete read is promoted to a complete
snapshot, and `baseline_advanced` is always false.

A complete report establishes enumeration under the configured markers. It does
not establish a consistent point-in-time snapshot, source identity matching,
peer agreement, replacement parity, or permission to write. Record revisions and
stable counts alone cannot prove snapshot consistency while an estate changes.
`data_ready_for_reconciliation` therefore remains false for every report. Validate
snapshot consistency and reconciliation mapping separately before any import.

The actual customer acceptance still requires:

1. Product/build, deployment, licensed API scope, installed modules, and approved
   read account; collect written access authorization from the customer.
2. Verified routes, response shapes, page-size behavior, terminal/count semantics,
   revision behavior, deletion/retirement semantics, and results across all pages.
3. Approved workflow, hierarchy, custom-field, identity-matching, writer, and
   field-ownership catalogs, plus representative sanitized failure fixtures.
4. Observed auth/session behavior, API version and metadata availability, entity
   inventory, topology/geometry availability, rate limits, and outage recovery.
   This harness does not guess a metadata route or infer unsupported entities.
5. Customer-observed load and server CPU at the D32 concurrency levels (1/2/4),
   operator acceptance results, and a supported-version matrix based on evidence.
   This bounded harness performs serial reads only; it is not a load test.
6. A separate approved staging plan for any future write/concurrency/read-back
   validation. No write probe exists in this harness.

Keep the D32 gate open until the customer evidence exists and has been reviewed.
A synthetic fixture pass proves harness behavior, not Nlyte compatibility.
