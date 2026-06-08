import json

from .manifest import Policy
from .sources.base import Sensitive


class _SafeDict(dict):
    def __missing__(self, key):
        return ""


class Config:
    def __init__(self, policy: Policy = None):
        self._policy = policy if policy is not None else []
        self._priorities = {}
        self._origins = {}
        self.conflicts = {}

    def set(self, key: str, value, origin: str, priority=0):
        if isinstance(value, dict):
            for k, v in value.items():
                self.set(f"{key}.{k}", v, origin, priority)
            return

        if hasattr(self, key):
            current = getattr(self, key)
            if self._equals(current, value):
                return
            self.conflicts.setdefault(key, [(self._origins.get(key, "?"), current)]).append(
                (origin, value)
            )
            if priority > self._priorities.get(key, 0):
                setattr(self, key, value)
                self._origins[key] = origin
                self._priorities[key] = priority
            return

        setattr(self, key, value)
        self._origins[key] = origin
        self._priorities[key] = priority

    def _equals(self, a, b):
        ua = a.unwrap() if isinstance(a, Sensitive) else a
        ub = b.unwrap() if isinstance(b, Sensitive) else b
        return ua == ub

    def _is_expected_divergence(self, key):
        for p in getattr(self._policy, "expected_divergence", []) or []:
            if p.endswith(".*") and (key == p[:-2] or key.startswith(p[:-2] + ".")):
                return True
            if key == p:
                return True
        return False

    def to_dict(self, mask=True):
        flat = {k: v for k, v in vars(self).items() if not k.startswith("_") and k != "conflicts"}
        nested = {}
        for dotted, value in flat.items():
            parts = dotted.split(".")
            cur = nested
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = value

        templates = getattr(self._policy, "connection_strings", {}) or {}
        out = {}
        for key, value in nested.items():
            tpl = templates.get(key)
            if tpl and isinstance(value, dict):
                data = (
                    value
                    if mask
                    else {
                        k: (v.unwrap() if isinstance(v, Sensitive) else v) for k, v in value.items()
                    }
                )
                out[f"{key}_url"] = tpl.format_map(_SafeDict(data))
            else:
                out[key] = self._mask(value, mask)
        return out

    def to_json(self, mask=True, indent=2):
        return json.dumps(self.to_dict(mask), indent=indent, default=str)

    def _mask(self, node, mask):
        if isinstance(node, Sensitive):
            return "***" if mask else node.unwrap()
        if isinstance(node, dict):
            return {k: self._mask(v, mask) for k, v in node.items()}
        return node
