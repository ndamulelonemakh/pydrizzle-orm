from pydrizzle_orm import (
    index,
    integer,
    pg_enum,
    pg_schema,
    pg_table,
    serial,
    text,
    timestamp,
    unique_index,
    uuid,
)

public = pg_schema("public")

post_status = pg_enum("post_status", ["draft", "published", "archived"], schema=public)

users = pg_table(
    "users",
    schema=public,
    id=uuid().primary_key().default_random(),
    email=text().not_null(),
    username=text().not_null(),
    bio=text(),
    created_at=timestamp().not_null().default_now(),
    indexes=[
        unique_index("users_email_key").on("email"),
        unique_index("users_username_key").on("username"),
    ],
)

posts = pg_table(
    "posts",
    schema=public,
    id=uuid().primary_key().default_random(),
    title=text().not_null(),
    slug=text().not_null(),
    body=text(),
    status=post_status().not_null().default("draft"),
    author_id=uuid().not_null().references(lambda: users.id),
    created_at=timestamp().not_null().default_now(),
    indexes=[
        unique_index("posts_slug_key").on("slug"),
        index("posts_author_idx").on("author_id"),
        index("posts_status_idx").on("status"),
    ],
)

comments = pg_table(
    "comments",
    schema=public,
    id=uuid().primary_key().default_random(),
    body=text().not_null(),
    post_id=uuid().not_null().references(lambda: posts.id),
    author_id=uuid().not_null().references(lambda: users.id),
    created_at=timestamp().not_null().default_now(),
    indexes=[
        index("comments_post_idx").on("post_id"),
    ],
)

tags = pg_table(
    "tags",
    schema=public,
    id=serial().primary_key(),
    name=text().not_null(),
    slug=text().not_null(),
    indexes=[
        unique_index("tags_slug_key").on("slug"),
    ],
)

post_tags = pg_table(
    "post_tags",
    schema=public,
    post_id=uuid().not_null().references(lambda: posts.id),
    tag_id=integer().not_null().references(lambda: tags.id),
    indexes=[
        index("post_tags_post_idx").on("post_id"),
        index("post_tags_tag_idx").on("tag_id"),
    ],
)
