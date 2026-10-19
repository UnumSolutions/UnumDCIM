#!/usr/bin/env python3
"""Lint/render every module and verify chart guards without a Kubernetes cluster."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parent.parent
CHART = ROOT / "deploy" / "helm" / "unum-module"
MODULES = ("inventory", "placement", "workflow", "synchronization", "registry")
IMAGE = "example.invalid/unum/module@sha256:" + "a" * 64
VALUES = {
    "image": IMAGE,
    "replicas": 2,
    "existingSecret": "ci-runtime",
    "migrationSecret": "ci-migration",
    "postgresCaSecret": "ci-postgres-ca",
    "allowedHosts": "module.example.invalid",
    "oidc": {
        "issuer": "https://identity.example.invalid/realms/unum",
        "audience": "unum-api",
        "jwksUri": "https://identity.example.invalid/jwks",
    },
}
REJECTIONS = (
    ("unknown-module", "module", "unknown", "module must name one implemented domain"),
    ("mutable-image", "image", "example.invalid/unum:latest", "image must be pinned"),
    ("invalid-digest", "image", "example.invalid/unum@sha256:abc", "image must be pinned"),
    ("single-replica", "replicas", 1, "requires at least two replicas"),
    ("missing-runtime-secret", "existingSecret", "", "existingSecret is required"),
    ("missing-migration-secret", "migrationSecret", "", "migrationSecret is required"),
    ("missing-postgres-ca", "postgresCaSecret", "", "postgresCaSecret is required"),
    ("missing-hosts", "allowedHosts", "", "allowedHosts is required"),
    ("missing-audience", "oidc.audience", "", "oidc.audience is required"),
    ("missing-issuer", "oidc.issuer", "", "oidc.issuer must be an HTTPS issuer"),
    ("http-issuer", "oidc.issuer", "http://identity.example.invalid", "oidc.issuer must be an HTTPS issuer"),
    ("missing-jwks", "oidc.jwksUri", "", "oidc.jwksUri must be a trusted HTTPS JWKS URI"),
    ("http-jwks", "oidc.jwksUri", "http://identity.example.invalid/jwks", "oidc.jwksUri must be a trusted HTTPS JWKS URI"),
)


def check_render(rendered, module):
    """Check packaging/security contracts in the actual rendered resources."""
    resources = list(yaml.safe_load_all(rendered))
    by_kind = {item["kind"]: item for item in resources}
    assert len(resources) == 4 and set(by_kind) == {"Deployment", "Job", "Service", "PodDisruptionBudget"}
    deployment, migration = by_kind["Deployment"], by_kind["Job"]
    assert deployment["spec"]["replicas"] == 2
    assert deployment["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"] == 0
    assert by_kind["Service"]["spec"]["type"] == "ClusterIP"
    assert by_kind["PodDisruptionBudget"]["spec"]["minAvailable"] == 1
    assert migration["metadata"]["annotations"]["helm.sh/hook"] == "pre-install,pre-upgrade"
    for resource, secret in ((deployment, "ci-runtime"), (migration, "ci-migration")):
        pod = resource["spec"]["template"]["spec"]
        assert pod["automountServiceAccountToken"] is False
        assert pod["securityContext"]["runAsNonRoot"] is True
        assert pod["securityContext"]["runAsUser"] == 10001
        container = pod["containers"][0]
        assert container["image"] == IMAGE
        assert container["envFrom"] == [{"secretRef": {"name": secret}}]
        security = container["securityContext"]
        assert security["readOnlyRootFilesystem"] is True
        assert security["allowPrivilegeEscalation"] is False
        assert security["capabilities"]["drop"] == ["ALL"]
        assert security["seccompProfile"]["type"] == "RuntimeDefault"
        env = {item["name"]: item["value"] for item in container["env"]}
        assert env["UNUM_SERVICE"] == module and env["UNUM_DEMO"] == "0"
        assert env["PGSSLMODE"] == "verify-full"
        assert env["PGSSLROOTCERT"] == "/etc/unum/postgres/ca.crt"
        volumes = {item["name"]: item for item in pod["volumes"]}
        assert volumes["postgres-ca"]["secret"]["secretName"] == "ci-postgres-ca"
        assert "emptyDir" in volumes["tmp"]
    service = deployment["spec"]["template"]["spec"]["containers"][0]
    assert service["readinessProbe"]["httpGet"]["path"] == "/ready"
    assert service["livenessProbe"]["httpGet"]["path"] == "/health"
    assert migration["spec"]["template"]["spec"]["containers"][0]["command"] == [
        "python", "manage.py", "migrate", "--noinput"
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helm", default="helm", help="Helm executable (CI pins the version)")
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".data/ci/deployment/helm")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    def run(name, arguments):
        completed = subprocess.run([args.helm, *arguments], cwd=ROOT, capture_output=True, text=True, timeout=60)
        (args.output_dir / f"{name}.log").write_text(completed.stdout + completed.stderr)
        return completed

    try:
        version = run("version", ["version", "--short"])
        version.check_returncode()
        print(version.stdout.strip(), flush=True)
        with tempfile.TemporaryDirectory(prefix="unum-helm-") as temporary:
            values_file = Path(temporary) / "values.json"
            for module in MODULES:
                values_file.write_text(json.dumps(VALUES | {"module": module}))
                lint = run(f"{module}-lint", ["lint", "--strict", str(CHART), "--values", str(values_file)])
                render = run(f"{module}-template", ["template", module, str(CHART), "--values", str(values_file)])
                (args.output_dir / f"{module}.yaml").write_text(render.stdout)
                errors = []
                if lint.returncode or render.returncode:
                    errors.append("helm lint/template failed; see command logs")
                else:
                    try:
                        check_render(render.stdout, module)
                    except (AssertionError, KeyError, TypeError, yaml.YAMLError) as error:
                        errors.append(f"rendered contract failed: {error!r}")
                results.append({"name": module, "passed": not errors, "errors": errors})
                print(f"{module}: {'FAIL' if errors else 'PASS'} (lint, render, resource contracts)", flush=True)
            for name, key, value, expected in REJECTIONS:
                values = deepcopy(VALUES) | {"module": "inventory"}
                target = values
                parts = key.split(".")
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = value
                values_file.write_text(json.dumps(values))
                render = run(name, ["template", "invalid", str(CHART), "--values", str(values_file)])
                passed = render.returncode != 0 and expected in render.stderr
                results.append({"name": name, "passed": passed, "expected_error": expected})
                print(f"{name}: {'PASS' if passed else 'FAIL'} (expected rejection)", flush=True)
    except (OSError, subprocess.SubprocessError) as error:
        results.append({"name": "tool-execution", "passed": False, "error": str(error)})
        print(f"FAIL: {error}", flush=True)
    finally:
        (args.output_dir / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if results and all(item["passed"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
