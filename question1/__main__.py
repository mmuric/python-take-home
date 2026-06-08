import argparse
import json
import logging
import sys

from .config import Config
from .manifest import ManifestError, load_manifest
from .sources.base import PolicyViolation, Sensitive

log = logging.getLogger("sporty-config")


def cmd_merge(manifest, args):
    config = Config(manifest.policy)
    all_violations = []
    for env in manifest.environments:
        for source in env.sources:
            data, violations = source.load()
            all_violations.extend(violations)
            for key, value in data.items():
                config.set(key, value, origin=f"{env.name}.{source.name}", priority=env.priority + source.priority)

    
    log.info("=== MERGED CONFIG ===")
    if args.dry_run:
        print(config.to_json())

    log.info("=== POLICY VIOLATIONS ===")
    # violations issues in config files
    for v in all_violations:
        if not args.dry_run:
            raise PolicyViolation("\n".join(violations))
        else:
            log.warning("policy: %s", v)

    log.info("=== CONFLICTS ===")
    # conflicts between sources and environments
    for key, items in config.conflicts.items():
        types = {type(v.unwrap() if isinstance(v, Sensitive) else v).__name__ for _, v in items}
        type_note = f"  [type mismatch: {' vs '.join(sorted(types))}]" if len(types) > 1 else ""
        if not args.dry_run:
            raise PolicyViolation(f"conflict => {key}: {items} {type_note}")
        else:
            log.warning("conflict => %s: %s%s", key, items, type_note)
    
    if not args.dry_run:
        with open("config.json", "w") as f:
            json.dump(config.to_dict(), f, indent=2)

    return 0


def cmd_diff(manifest, args):
    config = Config(manifest.policy)
    for env in manifest.environments:
        for source in env.sources:
            data, _ = source.load()
            for key, value in data.items():
                config.set(key, value, origin=f"{env.name}.{source.name}", priority=source.priority)

    for key, items in config.conflicts.items():
        types = {type(v.unwrap() if isinstance(v, Sensitive) else v).__name__ for _, v in items}
        type_note = f"  [type mismatch: {' vs '.join(sorted(types))}]" if len(types) > 1 else ""
        log.warning("conflict => %s: %s%s", key, items, type_note)

    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="sporty-config")
    p.add_argument("--manifest", default="environments.yaml")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("merge", help="merged config for one env")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_merge)

    d = sub.add_parser("diff", help="drift between two envs")
    d.set_defaults(func=cmd_diff)

    args = p.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as err:
        log.error("manifest: %s", err)
        return 2

    return args.func(manifest, args)


if __name__ == "__main__":
    commands = {"merge", "diff"}
    if not any(arg in commands for arg in sys.argv[1:]):
        global_flags_with_value = {"--manifest", "--log-level"}
        i = 1
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg in global_flags_with_value:
                i += 2
            elif any(arg.startswith(f + "=") for f in global_flags_with_value):
                i += 1

            else:
                break
        sys.argv.insert(i, "merge")

    sys.exit(main())
