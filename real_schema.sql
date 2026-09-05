-- RAW - social media for actual life
-- Run this in your Supabase SQL editor once, alongside supabase_schema.sql.
-- Tables are prefixed `real_` so RAW and RIOT AI can share one project.

create table if not exists real_users (
  id bigserial primary key,
  handle text unique not null,
  email text unique not null,
  password_hash text not null,
  display_name text,
  pronouns text default '',
  location text default '',
  bio text default '',
  dealing_with text default '',
  going_okay text default '',
  bad_at text default '',
  current_state text default 'mundane',
  avatar_color text default '#8a4a3a',
  created_at text,
  updated_at text
);

create table if not exists real_posts (
  id bigserial primary key,
  user_id bigint not null references real_users(id) on delete cascade,
  body text not null,
  state text not null,
  created_at text
);

create table if not exists real_comments (
  id bigserial primary key,
  post_id bigint not null references real_posts(id) on delete cascade,
  user_id bigint not null references real_users(id) on delete cascade,
  body text not null,
  created_at text
);

create table if not exists real_reactions (
  id bigserial primary key,
  post_id bigint not null references real_posts(id) on delete cascade,
  user_id bigint not null references real_users(id) on delete cascade,
  kind text not null,
  created_at text,
  unique (post_id, user_id, kind)
);

create table if not exists real_follows (
  id bigserial primary key,
  follower_id bigint not null references real_users(id) on delete cascade,
  followee_id bigint not null references real_users(id) on delete cascade,
  created_at text,
  unique (follower_id, followee_id)
);

create index if not exists real_posts_user_idx on real_posts (user_id, id desc);
create index if not exists real_comments_post_idx on real_comments (post_id, id);
create index if not exists real_reactions_post_idx on real_reactions (post_id);
create index if not exists real_follows_follower_idx on real_follows (follower_id);
create index if not exists real_follows_followee_idx on real_follows (followee_id);

-- Same posture as the rest of this project: RLS on, anon key allowed through,
-- because auth is enforced in the Flask layer. Tighten before this holds
-- anyone's real life but your own.
alter table real_users enable row level security;
alter table real_posts enable row level security;
alter table real_comments enable row level security;
alter table real_reactions enable row level security;
alter table real_follows enable row level security;

create policy "allow all" on real_users for all using (true) with check (true);
create policy "allow all" on real_posts for all using (true) with check (true);
create policy "allow all" on real_comments for all using (true) with check (true);
create policy "allow all" on real_reactions for all using (true) with check (true);
create policy "allow all" on real_follows for all using (true) with check (true);
