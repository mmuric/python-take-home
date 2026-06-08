class Sensitive:
    """Wrapper around a secret value so accidental str/repr prints ***."""

    def __init__(self, value):
        self._value = value

    def unwrap(self):
        return self._value

    def __str__(self):
        return "***"

    __repr__ = __str__


class SourceUnavailable(Exception): ...


class PolicyViolation(Exception): ...


SENSITIVE_HINTS = ("password", "secret", "token", "api_key", "credential", "passphrase")


class BaseSource:
    name = "base"
    priority = 0
    required = False

    def __init__(self):
        self.violations = []

    def load(self):
        raise NotImplementedError

    def _is_sensitive(self, dotted_key):
        k = dotted_key.lower()
        return any(h in k for h in SENSITIVE_HINTS)

    def _reject_if_sensitive(self, dotted_key):
        if self._is_sensitive(dotted_key):
            self.violations.append(
                f"{self.name}: sensitive key '{dotted_key}' found — must live in vault"
            )

    def _walk_and_validate(self, data, path=""):
        """Za sources koji vraćaju ceo dict (yaml/json/http).
        Rekurzivno hoda kroz nested strukturu i validira svaki leaf path."""
        for k, v in data.items():
            full_path = f"{path}.{k}" if path else k
            if isinstance(v, dict):
                self._walk_and_validate(v, full_path)
            else:
                self._reject_if_sensitive(full_path)
