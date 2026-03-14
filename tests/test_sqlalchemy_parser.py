from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

from pydrizzle_orm.parsers.sqlalchemy import parse_sqlalchemy_module


def _write_sqlalchemy_package(tmp_path: Path, package_name: str) -> Path:
    package_root = tmp_path / package_name
    models = package_root / "models"
    models.mkdir(parents=True)

    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "base.py").write_text(
        """\
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
""",
        encoding="utf-8",
    )
    (models / "__init__.py").write_text("", encoding="utf-8")
    (models / "users.py").write_text(
        """\
from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
""",
        encoding="utf-8",
    )
    (models / "posts.py").write_text(
        """\
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
""",
        encoding="utf-8",
    )

    return package_root


def _write_sqlalchemy_module(tmp_path: Path) -> Path:
    path = tmp_path / "sqlalchemy_models.py"
    path.write_text(
        """\
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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

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
""",
        encoding="utf-8",
    )
    return path


def test_parse_example_sqlalchemy_models(tmp_path: Path) -> None:
    path = _write_sqlalchemy_module(tmp_path)

    result = parse_sqlalchemy_module(path)

    assert {table.name for table in result.tables} == {
        "users",
        "posts",
        "tags",
        "comments",
        "post_tags",
    }

    users = next(table for table in result.tables if table.name == "users")
    posts = next(table for table in result.tables if table.name == "posts")
    tags = next(table for table in result.tables if table.name == "tags")

    assert users.schema == "public"
    assert any(index.name == "users_email_key" and index.unique for index in users.indexes)

    user_id = next(column for column in users.columns if column.python_name == "id")
    created_at = next(column for column in users.columns if column.python_name == "created_at")
    author_id = next(column for column in posts.columns if column.python_name == "author_id")
    status = next(column for column in posts.columns if column.python_name == "status")
    tag_id = next(column for column in tags.columns if column.python_name == "id")

    assert user_id.col_type == "uuid"
    assert user_id.default == "gen_random_uuid()"
    assert user_id.default_is_sql is True
    assert created_at.default == "now()"
    assert created_at.default_is_sql is True
    assert author_id.references is not None
    assert author_id.references.ref_schema == "public"
    assert author_id.references.ref_table == "users"
    assert author_id.references.ref_column == "id"
    assert status.col_type == "enum"
    assert status.default == "draft"
    assert status.default_is_sql is False
    assert tag_id.col_type == "serial"

    assert [(enum.name, enum.values) for enum in result.enums] == [
        ("PostStatus", ("draft", "published", "archived"))
    ]


def test_parse_sqlalchemy_dotted_package_walks_submodules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_sqlalchemy_package(tmp_path, "blogapp")
    monkeypatch.syspath_prepend(str(tmp_path))

    result = parse_sqlalchemy_module("blogapp.models")

    assert {table.name for table in result.tables} == {"users", "posts"}
    posts = next(table for table in result.tables if table.name == "posts")
    author_id = next(column for column in posts.columns if column.python_name == "author_id")
    assert author_id.references is not None
    assert author_id.references.ref_table == "users"
    assert author_id.references.ref_column == "id"


def test_parse_sqlalchemy_package_directory_walks_submodules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = _write_sqlalchemy_package(tmp_path, "shopapp")
    monkeypatch.chdir(tmp_path)

    result = parse_sqlalchemy_module(package_root / "models")

    assert {table.name for table in result.tables} == {"users", "posts"}
