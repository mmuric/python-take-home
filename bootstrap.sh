#!/usr/bin/env bash
# Dev bootstrap. SOURCE this from project root:
#   source bootstrap.sh
#
# Exports SPORTY_VAULT_KEY + sample env vars into the current shell only.
# Re-encrypts example secrets with the freshly generated key.
# Trap on EXIT removes the encrypted files when the shell exits.

(return 0 2>/dev/null) || {
  echo "ERROR: must be sourced, not executed: source bootstrap.sh"
  exit 1
}

if [ ! -f pyproject.toml ]; then
  echo "ERROR: source from sporty_tasks project root (pyproject.toml not found here)"
  return 1
fi

# 1. Vault key — lives only in this shell session
VAULT_KEY=$(uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
export VAULT_KEY

# 2. Re-encrypt example secrets with this key
uv run python <<'PYEOF'
import os, json
from pathlib import Path
from cryptography.fernet import Fernet

f = Fernet(os.environ["VAULT_KEY"].encode())
examples = Path("question1/examples")

staging = {
    "database_password": "staging-p@ss",
    "stripe_api_key":    "sk_test_staging_abc",
    "jwt_signing_key":   "staging-jwt-secret",
}
production = {
    "database_password": "prod-pr0d-pa55",
    "stripe_api_key":    "sk_live_prod_xyz",
    "jwt_signing_key":   "prod-jwt-secret",
}

(examples / "secrets.staging.enc").write_bytes(f.encrypt(json.dumps(staging).encode()))
(examples / "secrets.production.enc").write_bytes(f.encrypt(json.dumps(production).encode()))
PYEOF

# 3. Sample env vars for the EnvSource (dotted nesting via __)
export SPORTY_LOG_LEVEL=INFO
export SPORTY_WORKER_COUNT=8

export SPORTY_RABBITMQ__HOST=localhost
export SPORTY_RABBITMQ__PORT=5672
export SPORTY_RABBITMQ__USERNAME=guest
export SPORTY_RABBITMQ__PASSWORD=guest
# export SPORTY_RABBITMQ__VIRTUAL_HOST=

export SPORTY_REDIS__HOST=redis.example.com
export SPORTY_REDIS__PORT=6380
export SPORTY_REDIS__USERNAME=app_redis
export SPORTY_REDIS__PASSWORD=secret
export SPORTY_REDIS__SSL=true

# 4. Clean up encrypted files when this shell dies.
#    Env vars die with the shell automatically (no unset needed).
trap 'rm -f question1/examples/secrets.staging.enc question1/examples/secrets.production.enc 2>/dev/null' EXIT

echo "sporty_tasks dev shell ready (this shell only)"
echo "  VAULT_KEY:   set"
echo "  SPORTY_LOG_LEVEL:   $SPORTY_LOG_LEVEL"
echo "  SPORTY_RABBITMQ__*: 5 vars"
echo "  SPORTY_REDIS__*:    4 vars"
echo "  encrypted secrets:  question1/examples/secrets.{staging,production}.enc"
echo "  on shell exit:      encrypted files removed, env vars gone"
echo
echo "Try:  uv run python -m question1 show staging"
