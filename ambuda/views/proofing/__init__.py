from .pages import bp as _pages
from .projects import bp as _projects
from .site import bp
from .tagging import bp as _tagging
from .talk import bp as _talk


bp.register_blueprint(_pages)
bp.register_blueprint(_projects)
bp.register_blueprint(_tagging, url_prefix="/tagging")
bp.register_blueprint(_talk)
