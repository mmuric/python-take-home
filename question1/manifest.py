from pathlib import Path

import yaml

from .sources.env import EnvSource
from .sources.vault import VaultSource
from .sources.yaml_source import YamlSource


class Policy:
    def __init__(
        self,
        sensitive_keys=None,
        expected_divergence=None,
        fail_on_missing=True,
        connection_strings=None,
        vault_key_mapping=None,
    ):
        self.sensitive_keys = sensitive_keys or set()
        self.expected_divergence = expected_divergence or []
        self.fail_on_missing = fail_on_missing
        self.connection_strings = connection_strings or {}
        self.vault_key_mapping = vault_key_mapping or {}


class Environment:
    def __init__(self, name, sources, priority=0):
        self.name = name
        self.sources = sources
        self.priority = priority


class Manifest:
    def __init__(self, environments, policy):
        self.environments = environments
        self.policy = policy


class ManifestError(Exception):
    pass


def load_manifest(path):
    path = Path(path)
    with path.open() as f:
        raw = yaml.safe_load(f)

    policy_raw = raw.get("policy", {})
    policy = Policy(
        expected_divergence=policy_raw.get("expected_divergence_between_envs", []),
        fail_on_missing=policy_raw.get("fail_on_required_source_missing", True),
        connection_strings=policy_raw.get("connection_strings", {}),
        vault_key_mapping=policy_raw.get("vault_key_mapping", {}),
    )

    envs = []
    for name, spec in raw["environments"].items():
        envs.append(Environment(
            name=name,
            sources=_build_sources(spec.get("sources", []), policy),
            priority=spec.get("priority", 0)))

    return Manifest(environments=envs, policy=policy)


def _build_sources(specs, policy):
    out = []
    for spec in specs:
        t = spec.get("type")
        if t == "yaml":
            out.append(YamlSource(spec["path"], required=spec.get("required", True)))
        elif t == "env":
            out.append(
                EnvSource(prefix=spec.get("prefix", ""), required=spec.get("required", True))
            )
        elif t == "http":
            # TODO: out.append(HttpApiSource(spec["url"], token=..., timeout=..., ...))
            raise NotImplementedError("http source")
        elif t == "vault":
            out.append(
                VaultSource(
                    spec["path"],
                    key_env=spec.get("key_env", "SPORTY_VAULT_KEY"),
                    required=spec.get("required", True),
                    key_mapping=policy.vault_key_mapping,
                )
            )
        else:
            raise ManifestError(f"unknown source type: {t!r}")
    return out
