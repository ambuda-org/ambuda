"""Various site content unrelated to texts and proofing.

The idea is that a trusted user can edit site content directly without waiting
for a site deploy.
"""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy import Text as Text_
from sqlalchemy.orm import declarative_base

from ambuda.models.base import Base, foreign_key, pk


class Sponsorship(Base):

    """Models a project that a donor can sponsor."""

    __tablename__ = "site_sponsorship"

    #: Primary key.
    id = pk()
    #: Sanskrit title.
    sa_title = Column(String, nullable=False)
    #: English title.
    en_title = Column(String, nullable=False)
    #: Description.
    description = Column(Text_, nullable=False)
