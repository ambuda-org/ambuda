from flask import Blueprint, render_template


bp = Blueprint("debug", __name__)


@bp.route("/style")
def style():
    """Show CSS for common components on one page."""
    return render_template("debug/style.html")
