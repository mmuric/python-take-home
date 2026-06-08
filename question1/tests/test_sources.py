import json
import os

import pytest
import yaml
from cryptography.fernet import Fernet

from question1.__main__ import main
from question1.sources.base import PolicyViolation


@pytest.fixture(autouse=True)
def _clean_sporty_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("SPORTY_") or k == "VAULT_KEY":
            monkeypatch.delenv(k, raising=False)


def _write_vault(tmp_path, name, payload, key):
    p = tmp_path / name
    p.write_bytes(Fernet(key).encrypt(json.dumps(payload).encode()))
    return p


@pytest.fixture
def errored_env(tmp_path, monkeypatch):
    key = Fernet.generate_key()
    monkeypatch.setenv("VAULT_KEY", key.decode())
    monkeypatch.setenv("SPORTY_RABBITMQ__HOST", "rmq.local")
    monkeypatch.setenv("SPORTY_RABBITMQ__PASSWORD", "leaked")  # violation
    staging_yaml = tmp_path / "staging.yaml"
    staging_yaml.write_text(
        yaml.dump(
            {
                "database": {"host": "db-s", "port": 5432, "username": "u", "password": "leaked"},
                "log_level": "DEBUG",
            }
        )
    )
    production_yaml = tmp_path / "production.yaml"
    production_yaml.write_text(
        yaml.dump(
            {
                "database": {"host": "db-p", "port": 5432, "username": "u", "password": "leaked"},
                "log_level": "INFO",
            }
        )
    )

    staging_vault = _write_vault(tmp_path, "s.enc", {"database_password": "real-s"}, key)
    production_vault = _write_vault(tmp_path, "p.enc", {"database_password": "real-p"}, key)

    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        yaml.dump(
            {
                "environments": {
                    "staging": {
                        "sources": [
                            {"type": "yaml", "path": str(staging_yaml)},
                            {"type": "env", "prefix": "SPORTY_"},
                            {"type": "vault", "path": str(staging_vault), "key_env": "VAULT_KEY"},
                        ]
                    },
                    "production": {
                        "sources": [
                            {"type": "yaml", "path": str(production_yaml)},
                            {"type": "env", "prefix": "SPORTY_"},
                            {
                                "type": "vault",
                                "path": str(production_vault),
                                "key_env": "VAULT_KEY",
                            },
                        ]
                    },
                },
                "policy": {
                    "vault_key_mapping": {"database_password": "database.password"},
                    "connection_strings": {
                        "database": "postgresql://{username}:{password}@{host}:{port}/db",
                    },
                },
            }
        )
    )
    return manifest


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    key = Fernet.generate_key()
    monkeypatch.setenv("VAULT_KEY", key.decode())
    cfg = {"database": {"host": "db", "port": 5432, "username": "u"}, "log_level": "INFO"}
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(yaml.dump(cfg))
    vault_path = _write_vault(tmp_path, "vault.enc", {"database_password": "x"}, key)

    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        yaml.dump(
            {
                "environments": {
                    "staging": {
                        "sources": [
                            {"type": "yaml", "path": str(yaml_path)},
                            {"type": "vault", "path": str(vault_path), "key_env": "VAULT_KEY"},
                        ]
                    },
                    "production": {
                        "sources": [
                            {"type": "yaml", "path": str(yaml_path)},
                            {"type": "vault", "path": str(vault_path), "key_env": "VAULT_KEY"},
                        ]
                    },
                },
                "policy": {
                    "vault_key_mapping": {"database_password": "database.password"},
                    "connection_strings": {
                        "database": "postgresql://{username}:{password}@{host}:{port}/db",
                    },
                },
            }
        )
    )
    return manifest


def test_merge_dry_run_collects_issues(errored_env, capsys, caplog):
    code = main(["--manifest", str(errored_env), "merge", "--dry-run"])
    assert code == 0
    out = capsys.readouterr()
    log_text = caplog.text.lower()
    
    assert "policy" in log_text.lower()
    assert "conflict" in log_text.lower()
    assert "{" in out.out


def test_merge_strict_raises_on_violation(errored_env):
    with pytest.raises(PolicyViolation):
        main(["--manifest", str(errored_env), "merge"])


def test_diff_runs(errored_env, caplog):
    code = main(["--manifest", str(errored_env), "diff"])
    assert code == 0
    log_text = caplog.text.lower()
    assert "conflict" in log_text.lower()
    


def test_merge_clean_succeeds(clean_env, caplog, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    code = main(["--manifest", str(clean_env), "merge"])
    assert code == 0
    log_text = caplog.text.lower()
    assert "violation" not in log_text.lower()

    written = tmp_path / "config.json"
    assert written.exists()
    data = json.loads(written.read_text()) 
    assert data["database_url"] == "postgresql://u:***@db:5432/db"
    assert data["log_level"] == "INFO"
