import json
from dataclasses import dataclass

from ambuda.utils.json_serde import AmbudaJSONEncoder


@dataclass
class Dummy:
    foo: str
    bar: str


def test_encode():
    dummy = Dummy(foo="oof", bar="rab")
    assert json.dumps(dummy, cls=AmbudaJSONEncoder) == '{"foo": "oof", "bar": "rab"}'
