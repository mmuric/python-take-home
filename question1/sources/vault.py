import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .base import BaseSource, Sensitive, SourceUnavailable


class VaultSource(BaseSource):
    """Reads a Fernet-encrypted JSON file. Key comes from env var.
    Every value is treated as sensitive."""

    name = "vault"

    def __init__(
        self, path, key_env="SPORTY_VAULT_KEY", priority=40, required=False, key_mapping=None
    ):
        self.path = Path(path)
        self.key_env = key_env
        self.priority = priority
        self.required = required
        self.key_mapping = key_mapping or {}
        super().__init__()

    def load(self):
        if not self.path.exists():
            raise SourceUnavailable(f"vault file not found: {self.path}")

        key = os.environ.get(self.key_env)
        if not key:
            raise SourceUnavailable(f"missing key env var: {self.key_env}")

        try:
            plaintext = Fernet(key.encode()).decrypt(self.path.read_bytes())
        except InvalidToken as err:
            raise SourceUnavailable("vault decryption failed (wrong key or tampered file)") from err

        data = json.loads(plaintext)
        if not isinstance(data, dict):
            raise SourceUnavailable("vault payload must be a JSON object")

        result = {}
        for k, v in data.items():
            dotted = self.key_mapping.get(k, k)
            parts = dotted.split(".")
            current = result
            for p in parts[:-1]:
                current = current.setdefault(p, {})
            current[parts[-1]] = Sensitive(v)
        return result, self.violations
