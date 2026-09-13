"""Fail closed on unsupported module combinations. No installation side effects."""
from datetime import date
import re


def check_install(candidate, installed, today=None):
    today = today or date.today()
    errors = []
    if candidate.get("manifest_version") != 1:
        errors.append("Unsupported manifest version")
    if candidate.get("status") != "implemented":
        errors.append("Module is not implemented")
    artifact = candidate.get("artifact")
    if not isinstance(artifact, str) or not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", artifact):
        errors.append("An immutable artifact digest is required for installation")
    if not candidate.get("signature_verified", False):
        errors.append("Artifact signature must be verified by the installer")
    # A manifest cannot self-attest verification; the installer must supply this
    # value from its trusted verifier. The public endpoint always forces false.
    for dependency, required in candidate.get("requires", {}).items():
        peer = installed.get(dependency)
        if not peer:
            errors.append("Missing dependency: " + dependency)
            continue
        if required not in peer.get("provides", []):
            errors.append("Unsupported contract: " + dependency + "/" + required)
        tested = candidate.get("tested_with", {}).get(dependency, [])
        if peer.get("version") not in tested:
            errors.append("Untested version combination: " + dependency)
    until = candidate.get("supported_until")
    if not until or date.fromisoformat(until) < today:
        errors.append("Release is outside its support window")
    return errors
