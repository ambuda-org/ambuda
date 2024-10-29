import dataclasses
from json import JSONEncoder


class AmbudaJSONEncoder(JSONEncoder):
    """Extend Flask's default encoder to support dataclasses."""

    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)
