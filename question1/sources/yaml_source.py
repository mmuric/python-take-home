from pathlib import Path

import yaml

from .base import BaseSource


class YamlSource(BaseSource):
    name = "yaml"

    def __init__(self, path, priority=10, required=True):
        self.path = Path(path)
        self.required = required

        super().__init__()

    def load(self):
        path = Path(self.path)
        with path.open() as f:
            raw = yaml.safe_load(f)

        self._walk_and_validate(raw)
        return raw, self.violations
