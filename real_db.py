"""
RAW - Data layer for the real-life social network.

Same deal as database.py: Supabase in production, SQLite locally.
Tables are prefixed `real_` so they can share a Supabase project with RIOT AI.
"""

import os
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

if USE_SUPABASE:
    from supabase import create_client
    _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("🗄️  [RAW] Connected to Supabase")
else:
    _client = None
    print("🗄️  [RAW] Using local SQLite")

DB_FILE = Path(__file__).parent / "real_life.db"


# ── The vocabulary of the place ────────────────────────────────────────────────
# Every post has to be one of these. There is no "living my best life".

STATES = {
    'rough':      {'label': 'rough day',        'emoji': '🌧',  'color': '#5b6b8a'},
    'grinding':   {'label': 'grinding',         'emoji': '⚙️',  'color': '#7a6a55'},
    'mundane':    {'label': 'nothing special',  'emoji': '🥣',  'color': '#6b7a6b'},
    'small_win':  {'label': 'small win',        'emoji': '🌱',  'color': '#4f7f5a'},
    'spiraling':  {'label': 'spiraling',        'emoji': '🌀',  'color': '#7a4f6b'},
    'healing':    {'label': 'healing',          'emoji': '🩹',  'color': '#4f6f7f'},
    'angry':      {'label': 'angry',            'emoji': '🔥',  'color': '#8a4a3a'},
    'numb':       {'label': 'numb',             'emoji': '🌫',  'color': '#5f5f68'},
    'okay':       {'label': 'okay, actually',   'emoji': '☀️',  'color': '#7f7040'},
}

# Not likes. You cannot "like" someone's worst week.
REACTIONS = {
    'been_there': {'label': 'been there',  'emoji': '🫱'},
    'seen':       {'label': 'i see you',   'emoji': '👁'},
    'held':       {'label': 'holding this','emoji': '🤲'},
    'proud':      {'label': 'proud of you','emoji': '🪧'},
    'same':       {'label': 'same',        'emoji': '🪞'},
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Tiny dual-backend query layer ──────────────────────────────────────────────
# Both backends speak dicts. No joins anywhere — rows get stitched in Python so
# SQLite and Postgres behave identically.

SCHEMA = [
    '''CREATE TABLE IF NOT EXISTS real_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        handle TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        display_name TEXT,
        pronouns TEXT,
        location TEXT,
        bio TEXT,
        dealing_with TEXT,
        going_okay TEXT,
        bad_at TEXT,
        current_state TEXT DEFAULT 'mundane',
        avatar_color TEXT DEFAULT '#8a4a3a',
        created_at TEXT,
        updated_at TEXT )''',
    '''CREATE TABLE IF NOT EXISTS real_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        state TEXT NOT NULL,
        created_at TEXT )''',
    '''CREATE TABLE IF NOT EXISTS real_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT )''',
    '''CREATE TABLE IF NOT EXISTS real_reactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        created_at TEXT )''',
    '''CREATE TABLE IF NOT EXISTS real_follows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        follower_id INTEGER NOT NULL,
        followee_id INTEGER NOT NULL,
        created_at TEXT )''',
]


def init_sqlite():
    conn = sqlite3.connect(DB_FILE)
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    conn.close()


if not USE_SUPABASE:
    init_sqlite()


def _conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _insert(table: str, row: dict) -> dict:
    if USE_SUPABASE:
        res = _client.table(table).insert(row).execute()
        return res.data[0] if res.data else row
    cols = ','.join(row)
    marks = ','.join('?' * len(row))
    conn = _conn()
    cur = conn.execute(f'INSERT INTO {table} ({cols}) VALUES ({marks})', tuple(row.values()))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {**row, 'id': new_id}


def _update(table: str, row_id: int, changes: dict):
    if USE_SUPABASE:
        _client.table(table).update(changes).eq('id', row_id).execute()
        return
    sets = ','.join(f'{k}=?' for k in changes)
    conn = _conn()
    conn.execute(f'UPDATE {table} SET {sets} WHERE id=?', (*changes.values(), row_id))
    conn.commit()
    conn.close()


def _delete(table: str, **eq):
    if USE_SUPABASE:
        q = _client.table(table).delete()
        for k, v in eq.items():
            q = q.eq(k, v)
        q.execute()
        return
    where = ' AND '.join(f'{k}=?' for k in eq)
    conn = _conn()
    conn.execute(f'DELETE FROM {table} WHERE {where}', tuple(eq.values()))
    conn.commit()
    conn.close()


def _select(table: str, where: dict = None, where_in: tuple = None,
            order: str = None, desc: bool = True, limit: int = None) -> list:
    """where_in is ('column', [values]). Empty value list means empty result."""
    where = where or {}
    if where_in and not where_in[1]:
        return []

    if USE_SUPABASE:
        q = _client.table(table).select('*')
        for k, v in where.items():
            q = q.eq(k, v)
        if where_in:
            q = q.in_(where_in[0], where_in[1])
        if order:
            q = q.order(order, desc=desc)
        if limit:
            q = q.limit(limit)
        return q.execute().data or []

    clauses, params = [], []
    for k, v in where.items():
        clauses.append(f'{k}=?')
        params.append(v)
    if where_in:
        col, vals = where_in
        clauses.append(f'{col} IN ({",".join("?" * len(vals))})')
        params.extend(vals)
    sql = f'SELECT * FROM {table}'
    if clauses:
        sql += ' WHERE ' + ' AND '.join(clauses)
    if order:
        sql += f' ORDER BY {order} ' + ('DESC' if desc else 'ASC')
    if limit:
        sql += ' LIMIT ?'
        params.append(limit)
    conn = _conn()
    rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
    conn.close()
    return rows


def _one(table: str, **eq):
    rows = _select(table, where=eq, limit=1)
    return rows[0] if rows else None


# ── Users ──────────────────────────────────────────────────────────────────────

HANDLE_RE = re.compile(r'^[a-z0-9_]{3,20}$')


def normalize_handle(handle: str) -> str:
    return (handle or '').strip().lstrip('@').lower()


def handle_is_valid(handle: str) -> bool:
    return bool(HANDLE_RE.match(handle or ''))


def create_user(handle: str, email: str, password_hash: str, display_name: str) -> dict:
    ts = now()
    return _insert('real_users', {
        'handle': normalize_handle(handle),
        'email': email.strip().lower(),
        'password_hash': password_hash,
        'display_name': display_name.strip() or handle,
        'pronouns': '', 'location': '', 'bio': '',
        'dealing_with': '', 'going_okay': '', 'bad_at': '',
        'current_state': 'mundane',
        'avatar_color': _color_for(handle),
        'created_at': ts, 'updated_at': ts,
    })


def _color_for(seed: str) -> str:
    palette = ['#8a4a3a', '#4f7f5a', '#5b6b8a', '#7a4f6b', '#7f7040', '#4f6f7f', '#7a6a55']
    return palette[sum(ord(c) for c in (seed or 'x')) % len(palette)]


def get_user(user_id: int):
    return _one('real_users', id=user_id)


def get_user_by_handle(handle: str):
    return _one('real_users', handle=normalize_handle(handle))


def get_user_by_email(email: str):
    return _one('real_users', email=(email or '').strip().lower())


def get_users(ids) -> dict:
    """id -> user, for stitching feeds together."""
    ids = list({int(i) for i in ids})
    return {u['id']: u for u in _select('real_users', where_in=('id', ids))}


def update_profile(user_id: int, fields: dict):
    allowed = ('display_name', 'pronouns', 'location', 'bio',
               'dealing_with', 'going_okay', 'bad_at', 'current_state', 'avatar_color')
    changes = {k: (fields.get(k) or '').strip() for k in allowed if k in fields}
    if changes.get('current_state') not in STATES:
        changes.pop('current_state', None)
    if not changes:
        return
    changes['updated_at'] = now()
    _update('real_users', user_id, changes)


def list_users(limit: int = 60) -> list:
    return _select('real_users', order='id', desc=True, limit=limit)


# ── Posts ──────────────────────────────────────────────────────────────────────
# Posts are immutable on purpose. You can delete one. You cannot polish it.

def create_post(user_id: int, body: str, state: str) -> dict:
    if state not in STATES:
        state = 'mundane'
    return _insert('real_posts', {
        'user_id': user_id,
        'body': body.strip(),
        'state': state,
        'created_at': now(),
    })


def get_post(post_id: int):
    return _one('real_posts', id=post_id)


def delete_post(post_id: int):
    _delete('real_comments', post_id=post_id)
    _delete('real_reactions', post_id=post_id)
    _delete('real_posts', id=post_id)


def posts_by_users(user_ids, limit: int = 50) -> list:
    return _select('real_posts', where_in=('user_id', list(user_ids)),
                   order='id', desc=True, limit=limit)


def posts_by_user(user_id: int, limit: int = 50) -> list:
    return _select('real_posts', where={'user_id': user_id},
                   order='id', desc=True, limit=limit)


def recent_posts(limit: int = 50) -> list:
    return _select('real_posts', order='id', desc=True, limit=limit)


# ── Reactions ──────────────────────────────────────────────────────────────────

def toggle_reaction(post_id: int, user_id: int, kind: str) -> bool:
    """Returns True if the reaction is now on. One of each kind per person."""
    if kind not in REACTIONS:
        return False
    existing = _select('real_reactions',
                       where={'post_id': post_id, 'user_id': user_id, 'kind': kind}, limit=1)
    if existing:
        _delete('real_reactions', id=existing[0]['id'])
        return False
    _insert('real_reactions', {'post_id': post_id, 'user_id': user_id,
                               'kind': kind, 'created_at': now()})
    return True


def reactions_for_posts(post_ids) -> dict:
    """post_id -> list of reaction rows."""
    out = {int(p): [] for p in post_ids}
    for r in _select('real_reactions', where_in=('post_id', list(post_ids))):
        out.setdefault(r['post_id'], []).append(r)
    return out


# ── Comments ───────────────────────────────────────────────────────────────────

def create_comment(post_id: int, user_id: int, body: str) -> dict:
    return _insert('real_comments', {
        'post_id': post_id, 'user_id': user_id,
        'body': body.strip(), 'created_at': now(),
    })


def delete_comment(comment_id: int):
    _delete('real_comments', id=comment_id)


def get_comment(comment_id: int):
    return _one('real_comments', id=comment_id)


def comments_for_posts(post_ids) -> dict:
    out = {int(p): [] for p in post_ids}
    for c in _select('real_comments', where_in=('post_id', list(post_ids)), order='id', desc=False):
        out.setdefault(c['post_id'], []).append(c)
    return out


# ── Follows ────────────────────────────────────────────────────────────────────

def follow(follower_id: int, followee_id: int):
    if follower_id == followee_id:
        return
    if _select('real_follows', where={'follower_id': follower_id, 'followee_id': followee_id}, limit=1):
        return
    _insert('real_follows', {'follower_id': follower_id, 'followee_id': followee_id,
                             'created_at': now()})


def unfollow(follower_id: int, followee_id: int):
    _delete('real_follows', follower_id=follower_id, followee_id=followee_id)


def is_following(follower_id: int, followee_id: int) -> bool:
    return bool(_select('real_follows',
                        where={'follower_id': follower_id, 'followee_id': followee_id}, limit=1))


def following_ids(user_id: int) -> list:
    return [r['followee_id'] for r in _select('real_follows', where={'follower_id': user_id})]


def follower_ids(user_id: int) -> list:
    return [r['follower_id'] for r in _select('real_follows', where={'followee_id': user_id})]
