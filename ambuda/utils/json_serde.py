import dataclasses

from flask import json


class AmbudaJSONEncoder(json.JSONEncoder):
    """Extend Flask's default encoder to support dataclasses."""

    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)
