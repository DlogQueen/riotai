"""
RIOT AI - Database Layer
Supabase in production, SQLite locally
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime

# Detect environment
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

if USE_SUPABASE:
    from supabase import create_client
    _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("🗄️  [DB] Connected to Supabase")
else:
    _client = None
    print("🗄️  [DB] Using local SQLite")

DB_FILE = Path(__file__).parent / "riot_ai.db"


# ── SQLite fallback init ───────────────────────────────────────────────────────

def init_sqlite():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  role TEXT, content TEXT, persona TEXT,
                  model TEXT, emotion TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS memories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  key TEXT UNIQUE, value TEXT, category TEXT,
                  importance INTEGER DEFAULT 5,
                  created_at TEXT, updated_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_facts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  category TEXT, fact TEXT, confidence REAL DEFAULT 1.0,
                  source TEXT, created_at TEXT, updated_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS session_summaries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  summary TEXT, message_count INTEGER,
                  persona TEXT, created_at TEXT)''')
    conn.commit()
    conn.close()

if not USE_SUPABASE:
    init_sqlite()


# ── Chat History ───────────────────────────────────────────────────────────────

def save_message(role: str, content: str, persona: str, model: str, emotion: str):
    now = datetime.now().isoformat()
    if USE_SUPABASE:
        _client.table('chat_history').insert({
            'role': role, 'content': content, 'persona': persona,
            'model': model, 'emotion': emotion, 'timestamp': now
        }).execute()
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('INSERT INTO chat_history (role,content,persona,model,emotion,timestamp) VALUES (?,?,?,?,?,?)',
                     (role, content, persona, model, emotion, now))
        conn.commit()
        conn.close()


def get_recent_messages(limit: int = 20) -> list:
    if USE_SUPABASE:
        res = _client.table('chat_history').select('role,content').order('id', desc=True).limit(limit).execute()
        return list(reversed([{'role': r['role'], 'content': r['content']} for r in res.data]))
    else:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?', (limit,))
        rows = list(reversed(c.fetchall()))
        conn.close()
        return [{'role': r[0], 'content': r[1]} for r in rows]


def get_history(limit: int = 100) -> list:
    if USE_SUPABASE:
        res = _client.table('chat_history').select('role,content,persona,model,timestamp').order('id', desc=True).limit(limit).execute()
        return list(reversed(res.data))
    else:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT role,content,persona,model,timestamp FROM chat_history ORDER BY id DESC LIMIT ?', (limit,))
        rows = list(reversed(c.fetchall()))
        conn.close()
        return [{'role': r[0], 'content': r[1], 'persona': r[2], 'model': r[3], 'timestamp': r[4]} for r in rows]


def clear_history():
    if USE_SUPABASE:
        _client.table('chat_history').delete().neq('id', 0).execute()
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('DELETE FROM chat_history')
        conn.commit()
        conn.close()


def count_messages() -> int:
    if USE_SUPABASE:
        res = _client.table('chat_history').select('id', count='exact').execute()
        return res.count or 0
    else:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM chat_history')
        count = c.fetchone()[0]
        conn.close()
        return count


# ── Memories ───────────────────────────────────────────────────────────────────

def db_save_memory(key: str, value: str, category: str = 'general', importance: int = 5):
    now = datetime.now().isoformat()
    if USE_SUPABASE:
        _client.table('memories').upsert({
            'key': key, 'value': value, 'category': category,
            'importance': importance, 'updated_at': now
        }, on_conflict='key').execute()
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('''INSERT OR REPLACE INTO memories (key,value,category,importance,created_at,updated_at)
                        VALUES (?,?,?,?,COALESCE((SELECT created_at FROM memories WHERE key=?),?),?)''',
                     (key, value, category, importance, key, now, now))
        conn.commit()
        conn.close()


def db_save_fact(category: str, fact: str, source: str = 'conversation', confidence: float = 1.0):
    now = datetime.now().isoformat()
    if USE_SUPABASE:
        # Check duplicate
        res = _client.table('user_facts').select('id').eq('category', category).eq('fact', fact).execute()
        if not res.data:
            _client.table('user_facts').insert({
                'category': category, 'fact': fact,
                'confidence': confidence, 'source': source,
                'created_at': now, 'updated_at': now
            }).execute()
    else:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT id FROM user_facts WHERE category=? AND fact=?', (category, fact))
        if not c.fetchone():
            conn.execute('INSERT INTO user_facts (category,fact,confidence,source,created_at,updated_at) VALUES (?,?,?,?,?,?)',
                         (category, fact, confidence, source, now, now))
            conn.commit()
        conn.close()


def db_get_all_memories() -> dict:
    if USE_SUPABASE:
        facts_res = _client.table('user_facts').select('category,fact').order('category').execute()
        mem_res = _client.table('memories').select('key,value,category,importance').order('importance', desc=True).execute()
        sum_res = _client.table('session_summaries').select('summary,created_at').order('created_at', desc=True).limit(5).execute()

        facts = {}
        for r in facts_res.data:
            cat = r['category']
            if cat not in facts:
                facts[cat] = []
            facts[cat].append(r['fact'])

        return {
            'facts': facts,
            'named': mem_res.data,
            'summaries': sum_res.data
        }
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('SELECT category, fact FROM user_facts ORDER BY category, created_at DESC')
        facts = {}
        for row in c.fetchall():
            cat = row['category']
            if cat not in facts:
                facts[cat] = []
            facts[cat].append(row['fact'])

        c.execute('SELECT key, value, category, importance FROM memories ORDER BY importance DESC, updated_at DESC')
        named = [dict(r) for r in c.fetchall()]

        c.execute('SELECT summary, created_at FROM session_summaries ORDER BY created_at DESC LIMIT 5')
        summaries = [dict(r) for r in c.fetchall()]

        conn.close()
        return {'facts': facts, 'named': named, 'summaries': summaries}


def db_save_summary(summary: str, message_count: int, persona: str):
    now = datetime.now().isoformat()
    if USE_SUPABASE:
        _client.table('session_summaries').insert({
            'summary': summary, 'message_count': message_count,
            'persona': persona, 'created_at': now
        }).execute()
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('INSERT INTO session_summaries (summary,message_count,persona,created_at) VALUES (?,?,?,?)',
                     (summary, message_count, persona, now))
        conn.commit()
        conn.close()
