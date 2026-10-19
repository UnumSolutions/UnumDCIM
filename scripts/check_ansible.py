#!/usr/bin/env python3
"""Parse the example inventory and lint the playbook; never connect to hosts."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".data/ci/deployment/ansible")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    commands = {
        "version": ["ansible-lint", "--version"],
        "syntax": ["ansible-playbook", "--syntax-check", "--inventory", "deploy/linux/inventory.example.yml", "deploy/linux/site.yml"],
        "lint": ["ansible-lint", "--offline", "--strict", "deploy/linux/site.yml"],
    }
    results = []
    with tempfile.TemporaryDirectory(prefix="unum-ansible-") as temporary:
        env = os.environ | {
            "ANSIBLE_HOME": str(Path(temporary) / "ansible"),
            "ANSIBLE_LOCAL_TEMP": str(Path(temporary) / "local"),
            "XDG_CACHE_HOME": str(Path(temporary) / "cache"),
        }
        for name, command in commands.items():
            try:
                completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
                output = completed.stdout + completed.stderr
                passed = completed.returncode == 0
            except (OSError, subprocess.SubprocessError) as error:
                output, passed = str(error), False
            (args.output_dir / f"{name}.log").write_text(output)
            results.append({"name": name, "passed": passed})
            print(f"{name}: {'PASS' if passed else 'FAIL'}\n{output}", flush=True)
    (args.output_dir / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if all(item["passed"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
