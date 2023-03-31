"""Models for discussion forums."""

from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy import Text as Text_
from sqlalchemy.orm import relationship

from ambuda.models.base import db, foreign_key, pk, same_as


def string():
    """Create a non-nullable string column that defaults to the empty string."""
    return Column(String, nullable=False, default="")


class Board(db.Model):

    """A list of threads."""

    __tablename__ = "discussion_boards"

    #: Primary key.
    id = pk()
    title = string()

    #: Threads, newest first.
    threads = relationship(
        "Thread", order_by=lambda: Thread.created_at.desc(), backref="board"
    )
    #: Posts, newest first.
    posts = relationship(
        "Post", order_by=lambda: Post.created_at.desc(), backref="board"
    )


class Thread(db.Model):

    """A list of posts."""

    __tablename__ = "discussion_threads"

    #: Primary key.
    id = pk()
    #: The thread title.
    title = string()
    #: The board this thread belongs to.
    board_id = foreign_key("discussion_boards.id")
    #: The author of this thread.
    author_id = foreign_key("users.id")
    #: Timestamp at which this thread was created.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    #: Timestamp at which this thread was updated.
    updated_at = Column(DateTime, default=same_as("created_at"), nullable=False)

    #: The author of this thread.
    author = relationship("User", backref="threads")
    #: Posts, oldest first.
    posts = relationship("Post", order_by=lambda: Post.created_at, backref="thread")


class Post(db.Model):

    """A post."""

    __tablename__ = "discussion_posts"

    #: Primary key.
    id = pk()

    #: The board this post belongs to.
    board_id = foreign_key("discussion_boards.id")
    #: The thread this post belongs to.
    thread_id = foreign_key("discussion_threads.id")
    #: The author of this post.
    author_id = foreign_key("users.id")
    #: Timestamp at which this post was created.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    #: Timestamp at which this post was updated (e.g. during an edit).
    updated_at = Column(DateTime, default=same_as("created_at"), nullable=False)

    #: The post content.
    content = Column(Text_, nullable=False)

    #: The author of this post.
    author = relationship("User", backref="posts")

    def update_content(self, new_content: str):
        """Update the post's content and its timestamp."""
        self.content = new_content
        self.updated_at = datetime.utcnow()
