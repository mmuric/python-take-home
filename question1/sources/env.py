import os

from .base import BaseSource

SENSITIVE_HINTS = ("password", "secret", "token", "api_key", "credential", "passphrase")


class EnvSource(BaseSource):
    name = "env"

    def __init__(self, prefix="", separator="__", priority=30, required=False):
        self.prefix = prefix
        self.separator = separator
        self.priority = priority
        self.required = required

        super().__init__()

    def load(self):
        result = {}

        for key, value in os.environ.items():
            if not key.startswith(self.prefix):
                continue
            rest = key.removeprefix(self.prefix)
            keys = [k.lower() for k in rest.split(self.separator)]
            dotted = ".".join(keys)
            self._reject_if_sensitive(dotted)

            current = result
            for k in keys[:-1]:
                current = current.setdefault(k, {})
            current[keys[-1]] = value
        return result, self.violations
