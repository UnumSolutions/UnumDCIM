"""Offline JSON rehearsal: python3 -m unum_sync examples/coexistence.json."""

import argparse
from dataclasses import asdict
import json

from .reconcile import Scope, Snapshot, plan


def main():
    parser = argparse.ArgumentParser(description="Offline Nlyte coexistence diff (no network or writes)")
    parser.add_argument("fixture")
    args = parser.parse_args()
    try:
        with open(args.fixture) as stream:
            data = json.load(stream)
        scope = Scope(**data["scope"])

        def snapshot(system, raw):
            return Snapshot(scope=scope, system=system, **raw)

        result = plan(
            scope=scope, baseline=data["baseline"], owners=data["owners"],
            nlyte=snapshot("nlyte", data["current"]["nlyte"]),
            unum=snapshot("unum", data["current"]["unum"]),
            previous={s: snapshot(s, v) for s, v in data["previous"].items()}
            if "previous" in data else None,
            writable={s: frozenset(v) for s, v in data.get("writable", {}).items()})
        print(json.dumps([asdict(d) for d in result], indent=2))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.exit(2, "Cannot plan: %s\n" % exc)


if __name__ == "__main__":
    main()
