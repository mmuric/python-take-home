# Question 1 — Configuration Conflict Resolver

## Files

```
/
├── question1/
│   ├── __main__.py           # CLI entry point
│   ├── config.py             # Config class — merge + conflict + render
│   ├── manifest.py           # Manifest loader + Policy + Environment dataclasses
│   ├── sources/
│       ├── base.py           # BaseSource, Sensitive, exceptions, validators
│       ├── env.py            # EnvSource (os.environ + prefix + nested via __)
│       ├── yaml_source.py    # YamlSource (file + walk-and-validate)
│       └── vault.py          # VaultSource (Fernet-encrypted file)
│   ├── examples/             # sample yaml + encrypted vault files
└    └── tests/                # pytest e2e and unit tests
```

# Setup

## Requirements

This project uses `uv` for dependency management and command execution.

Run `uv sync` from the project root (`/`). Make sure you execute the command from the root directory.

After `uv sync`, run:

```
source bootstrap.sh
```
This script sets the Vault token, Vault-related variables, and environment variables with the SPORTY_ prefix.

## Linting and Formatting

From the project root (`/`), run:
```
uv run ruff check question1
uv run ruff check question1 --fix
uv run ruff format question1
```

## Running the Tool

To merge configuration from both project environments (`stage` and `production`) and all supported sources (`yaml`, environment variables `env`, and `Vault`), run:
```
uv run python -m question1
```

This is a strict command that raises a PolicyViolation exception on the first detected issue.

It is also the default command, so the following is equivalent:

```
 uv run python -m question1 merge
```
If no conflicts or policy violations are found, the command generates a config.json file in the project root.

### Dry Run Mode

To inspect conflicts and policy violations without generating the output file, run:
```
uv run python -m question1 --dry-run
```
or 
```
uv run python -m question1 merge --dry-run
```

This command reports all detected conflicts and policy violations across:
1. environments (stage and production)
2. configuration sources (yaml, environment variables, and Vault)

### Environment Diff

To compare configuration differences between the `stage` and `production` environments, run:

```
uv run python -m question1 diff
```
This command displays all configuration values that differ between the two environments.

## Tests

You can run the tests using the following command from the project root (`/`):

```
uv run pytest question1/tests -s -v 
```