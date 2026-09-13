#!/usr/bin/env python3
"""Run explicitly configured read-only discovery or sanitized offline replay."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from unum_sync.discovery import DiscoveryConfig, DiscoveryError, discover, fixture_transport


def read_json(path, limit):
    with open(path, "rb") as handle:
        content = handle.read(limit + 1)
    if len(content) > limit:
        raise DiscoveryError("local_file_size_limit")
    return json.loads(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="Local verified routes, field mappings, and read limits")
    parser.add_argument("--fixture", type=Path, help="Sanitized response fixture; disables all network access")
    parser.add_argument("--output", type=Path, help="Create a new aggregate report; existing files are never replaced")
    args = parser.parse_args(argv)
    try:
        config = DiscoveryConfig.from_dict(read_json(args.config, 1_000_000))
        if args.fixture:
            transport = fixture_transport(read_json(args.fixture, 20_000_000))
            report = discover(config, transport=transport, mode="fixture")
        else:
            report = discover(config, token=os.environ.get(config.token_env))
        rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            # Exclusive creation prevents accidental replacement of a baseline,
            # fixture, or previous evidence report. Raw records are never output.
            descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as handle:
                handle.write(rendered)
        else:
            print(rendered, end="")
        return 0 if report["complete"] else 1
    except DiscoveryError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
    except (ValueError, UnicodeError, RecursionError, TypeError, KeyError):
        print(json.dumps({"error": "invalid_local_json"}), file=sys.stderr)
    except OSError:
        print(json.dumps({"error": "local_file_error"}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
