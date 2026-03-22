-- RIOT AI - Supabase Schema
-- Run this in your Supabase SQL editor once

create table if not exists chat_history (
  id bigserial primary key,
  role text not null,
  content text not null,
  persona text,
  model text,
  emotion text,
  timestamp text
);

create table if not exists memories (
  id bigserial primary key,
  key text unique not null,
  value text not null,
  category text default 'general',
  importance integer default 5,
  created_at text,
  updated_at text
);

create table if not exists user_facts (
  id bigserial primary key,
  category text not null,
  fact text not null,
  confidence real default 1.0,
  source text default 'conversation',
  created_at text,
  updated_at text
);

create table if not exists session_summaries (
  id bigserial primary key,
  summary text not null,
  message_count integer,
  persona text,
  created_at text
);

-- Enable RLS but allow all for anon key (you can tighten this later)
alter table chat_history enable row level security;
alter table memories enable row level security;
alter table user_facts enable row level security;
alter table session_summaries enable row level security;

create policy "allow all" on chat_history for all using (true) with check (true);
create policy "allow all" on memories for all using (true) with check (true);
create policy "allow all" on user_facts for all using (true) with check (true);
create policy "allow all" on session_summaries for all using (true) with check (true);
