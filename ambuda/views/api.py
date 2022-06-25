"""Views for API endpoints.

Other view modules import the `bp` blueprint below and use it to decorate API
endpoints.
"""

from flask import Blueprint


bp = Blueprint("api", __name__)
