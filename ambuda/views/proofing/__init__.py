"""Everything related to our proofing and transcription work."""

from . import main, page, project, tagging, talk, user


__all__ = ["bp"]


bp = main.bp
bp.register_blueprint(project.bp)
bp.register_blueprint(page.bp)
bp.register_blueprint(tagging.bp, url_prefix="/tagging")
bp.register_blueprint(talk.bp)
bp.register_blueprint(user.bp, url_prefix="/users")
