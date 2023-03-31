"""Various site content unrelated to texts and proofing.

The idea is that a trusted user can edit site content by creating and modifyng
these objects. By doing so, they can update the site without waiting for a site
deploy.
"""

from sqlalchemy import Column, Integer, String
from sqlalchemy import Text as Text_

from ambuda.models.base import db, pk


class ProjectSponsorship(db.Model):

    """A project that a donor can sponsor."""

    __tablename__ = "site_project_sponsorship"

    #: Primary key.
    id = pk()
    #: Sanskrit title.
    sa_title = Column(String, nullable=False)
    #: English title.
    en_title = Column(String, nullable=False)
    #: A short description of this project.
    description = Column(Text_, nullable=False)
    #: The estimated cost of this project in Indian rupees (INR).
    cost_inr = Column(Integer, nullable=False)
