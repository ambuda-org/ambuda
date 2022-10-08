"""Debug routes that are useful during development.

NOTE: In production, this module is not imported, and these routes are not
available. So, the code here is allowed to be slow, unsafe, etc.
"""

from flask import Blueprint, render_template

bp = Blueprint("debug", __name__)


@bp.route("/style")
def style():
    """Show CSS for common components on one page."""
    return render_template("debug/style.html")
