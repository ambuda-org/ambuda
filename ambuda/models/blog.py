from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy import Text as Text_
from sqlalchemy.orm import relationship

from ambuda.models.base import db, foreign_key, pk, same_as


class BlogPost(db.Model):

    """A blog post."""

    __tablename__ = "blog_posts"

    #: Primary key.
    id = pk()

    #: The author of this post.
    author_id = foreign_key("users.id")
    #: Timestamp at which this post was created.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    #: Timestamp at which this post was updated (e.g. during an edit).
    updated_at = Column(DateTime, default=same_as("created_at"), nullable=False)

    #: The post title.
    title = Column(String, nullable=False)
    #: The post slug.
    slug = Column(String, unique=True, nullable=False)
    #: The post content.
    content = Column(Text_, nullable=False)

    #: The author of this post.
    author = relationship("User")

    def update_content(self, new_content: str):
        """Update the post's content and its timestamp."""
        self.content = new_content
        self.updated_at = datetime.utcnow()
