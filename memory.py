"""
Coach Bear AI - Memory Engine ("Coach's Notebook")
Uses database.py abstraction (Supabase or SQLite)
"""

import json
import re
from openai import OpenAI
from database import (
    db_save_memory, db_save_fact, db_get_all_memories,
    db_save_summary, save_message
)


def save_memory(key: str, value: str, category: str = 'general', importance: int = 5):
    db_save_memory(key, value, category, importance)


def save_fact(category: str, fact: str, source: str = 'conversation', confidence: float = 1.0):
    db_save_fact(category, fact, source, confidence)


def get_all_memories() -> dict:
    return db_get_all_memories()


def build_memory_context() -> str:
    mem = get_all_memories()
    parts = []

    if mem['facts']:
        parts.append("WHAT YOU KNOW ABOUT THIS PERSON:")
        for category, facts in mem['facts'].items():
            parts.append(f"  [{category.upper()}]")
            for fact in facts[:5]:
                parts.append(f"    - {fact}")

    if mem['named']:
        parts.append("\nSAVED MEMORIES:")
        for m in mem['named'][:10]:
            parts.append(f"  [{m['category']}] {m['key']}: {m['value']}")

    if mem['summaries']:
        parts.append("\nRECENT SESSION SUMMARIES:")
        for s in mem['summaries'][:3]:
            ts = s.get('created_at', '')[:10]
            parts.append(f"  ({ts}) {s['summary']}")

    return '\n'.join(parts) if parts else ""


def extract_facts_from_message(message: str, api_key: str):
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "system",
                "content": """Extract memorable facts about the speaker from their message.
Return JSON array: [{"category": "...", "fact": "..."}]
Categories: identity, preferences, work, relationships, goals, emotions, skills, location, history
Only extract clear specific facts. Return [] if nothing memorable."""
            }, {
                "role": "user", "content": message
            }],
            max_tokens=300,
            temperature=0.1
        )
        raw = resp.choices[0].message.content.strip()
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            facts = json.loads(match.group())
            for f in facts:
                if 'category' in f and 'fact' in f:
                    save_fact(f['category'], f['fact'], source='auto-extract')
    except Exception as e:
        print(f"⚠️ [MEMORY] Fact extraction failed: {e}")


def save_session_summary(messages: list, persona: str, api_key: str):
    if len(messages) < 4:
        return
    try:
        client = OpenAI(api_key=api_key)
        convo = '\n'.join([f"{m['role'].upper()}: {m['content'][:200]}" for m in messages[-20:]])
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"Summarize this conversation in 2-3 sentences:\n\n{convo}"}],
            max_tokens=150,
            temperature=0.3
        )
        summary = resp.choices[0].message.content.strip()
        db_save_summary(summary, len(messages), persona)
        print(f"💾 [MEMORY] Session summarized")
    except Exception as e:
        print(f"⚠️ [MEMORY] Summary failed: {e}")
