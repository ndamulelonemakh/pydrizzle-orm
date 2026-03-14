import { sql } from 'drizzle-orm';
import {
  index,
  integer,
  pgEnum,
  pgSchema,
  pgTable,
  serial,
  text,
  timestamp,
  unique,
  uuid,
} from 'drizzle-orm/pg-core';

const publicSchema = pgSchema('public');

export const postStatusEnum = publicSchema.enum('post_status', [
  'draft',
  'published',
  'archived',
]);

export const users = publicSchema.table(
  'users',
  {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    email: text('email').notNull(),
    username: text('username').notNull(),
    bio: text('bio'),
    createdAt: timestamp('created_at').notNull().defaultNow(),
  },
  (table) => ({
    usersEmailKey: unique('users_email_key').on(table.email),
    usersUsernameKey: unique('users_username_key').on(table.username),
  }),
);

export const posts = publicSchema.table(
  'posts',
  {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    title: text('title').notNull(),
    slug: text('slug').notNull(),
    body: text('body'),
    status: postStatusEnum('status').notNull().default('draft'),
    authorId: uuid('author_id')
      .notNull()
      .references(() => users.id),
    createdAt: timestamp('created_at').notNull().defaultNow(),
  },
  (table) => ({
    postsSlugKey: unique('posts_slug_key').on(table.slug),
    postsAuthorIdx: index('posts_author_idx').on(table.authorId),
    postsStatusIdx: index('posts_status_idx').on(table.status),
  }),
);

export const comments = publicSchema.table(
  'comments',
  {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    body: text('body').notNull(),
    postId: uuid('post_id')
      .notNull()
      .references(() => posts.id),
    authorId: uuid('author_id')
      .notNull()
      .references(() => users.id),
    createdAt: timestamp('created_at').notNull().defaultNow(),
  },
  (table) => ({
    commentsPostIdx: index('comments_post_idx').on(table.postId),
  }),
);

export const tags = publicSchema.table(
  'tags',
  {
    id: serial('id').primaryKey(),
    name: text('name').notNull(),
    slug: text('slug').notNull(),
  },
  (table) => ({
    tagsSlugKey: unique('tags_slug_key').on(table.slug),
  }),
);

export const postTags = publicSchema.table(
  'post_tags',
  {
    postId: uuid('post_id')
      .notNull()
      .references(() => posts.id),
    tagId: integer('tag_id')
      .notNull()
      .references(() => tags.id),
  },
  (table) => ({
    postTagsPostIdx: index('post_tags_post_idx').on(table.postId),
    postTagsTagIdx: index('post_tags_tag_idx').on(table.tagId),
  }),
);
