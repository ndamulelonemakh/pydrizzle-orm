from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class PostStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="users_email_key"),
        UniqueConstraint("username", name="users_username_key"),
        {"schema": "public"},
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    posts: Mapped[list[Post]] = relationship(back_populates="author")
    comments: Mapped[list[Comment]] = relationship(back_populates="author")


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint("slug", name="posts_slug_key"),
        Index("posts_author_idx", "author_id"),
        Index("posts_status_idx", "status"),
        {"schema": "public"},
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, server_default=func.gen_random_uuid())
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PostStatus] = mapped_column(nullable=False, default=PostStatus.draft)
    author_id: Mapped[str] = mapped_column(ForeignKey("public.users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    author: Mapped[User] = relationship(back_populates="posts")
    comments: Mapped[list[Comment]] = relationship(back_populates="post")
    tags: Mapped[list[Tag]] = relationship(secondary="public.post_tags", back_populates="posts")


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("comments_post_idx", "post_id"),
        {"schema": "public"},
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, server_default=func.gen_random_uuid())
    body: Mapped[str] = mapped_column(Text, nullable=False)
    post_id: Mapped[str] = mapped_column(ForeignKey("public.posts.id"), nullable=False)
    author_id: Mapped[str] = mapped_column(ForeignKey("public.users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    post: Mapped[Post] = relationship(back_populates="comments")
    author: Mapped[User] = relationship(back_populates="comments")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("slug", name="tags_slug_key"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)

    posts: Mapped[list[Post]] = relationship(secondary="public.post_tags", back_populates="tags")


class PostTag(Base):
    __tablename__ = "post_tags"
    __table_args__ = (
        Index("post_tags_post_idx", "post_id"),
        Index("post_tags_tag_idx", "tag_id"),
        {"schema": "public"},
    )

    post_id: Mapped[str] = mapped_column(ForeignKey("public.posts.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("public.tags.id"), primary_key=True)
