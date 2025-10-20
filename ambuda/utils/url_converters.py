"""URL converters for Flask routes.

Flask supports a simple routing syntax [1] that understands various kinds of
URL arguments. This module contains extensions to this syntax.

[1]: https://flask.palletsprojects.com/en/2.2.x/api/#url-route-registrations
"""

import re

from werkzeug.routing import BaseConverter


class ListConverter(BaseConverter):
    """Converter for list data. Empty entries are ignored.

    Usage:

        # Application
        app = Flask(__name___)
        app.url_map.converters["list"] = ListConverter

    Then:

        # Views
        @app.route("/items/<list:ids>")
        def items(ids):
            ...
    """

    def to_python(self, s: str) -> list[str]:
        return [x for x in re.split("[,+]", s) if x]

    def to_url(self, values: list[str]) -> str:
        return ",".join(x for x in values if x)
