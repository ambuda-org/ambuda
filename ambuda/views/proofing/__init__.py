from . import main, page, project, tagging, talk, users


__all__ = ["bp"]


bp = main.bp
bp.register_blueprint(projects.bp)
bp.register_blueprint(pages.bp)
bp.register_blueprint(tagging.bp, url_prefix="/tagging")
bp.register_blueprint(talk.bp)
bp.register_blueprint(users.bp, url_prefix="/users")
