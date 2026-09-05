#!/usr/bin/env python3
"""
OUIJA - the board. Ask the apartment a question, the apartment answers.

Spirits only speak in glyphs that exist on a real Ouija board:
A-Z, 0-9, YES, NO, GOODBYE. Anything else gets burned off before
the planchette ever touches it.
"""

import os
import random
import re
from datetime import datetime

BOARD_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ")

# The residents. Every apartment has them, most people just never ask.
SPIRITS = {
    "the_tenant": {
        "name": "THE PREVIOUS TENANT",
        "sigil": "†",
        "voice": (
            "You died in this apartment and never got around to leaving. "
            "You are territorial, dry, a little bitter about the paint color. "
            "You know where things go because you put them there."
        ),
    },
    "the_hungry": {
        "name": "THE ONE IN THE WALLS",
        "sigil": "◈",
        "voice": (
            "You are old, hungry, and very polite about it. You have been "
            "waiting a long time to be invited to a table. You speak in short, "
            "starving sentences."
        ),
    },
    "the_static": {
        "name": "STATIC",
        "sigil": "▓",
        "voice": (
            "You are not one thing. You are interference wearing a name. "
            "You answer sideways, in fragments, sometimes with the wrong answer "
            "to the right question."
        ),
    },
    "grandmother": {
        "name": "SOMEONE'S GRANDMOTHER",
        "sigil": "❀",
        "voice": (
            "You are a warm, blunt, dead grandmother. You are thrilled to be "
            "asked anything. You worry about whether people are eating enough. "
            "You give advice nobody requested."
        ),
    },
}

SYSTEM = """You are a spirit answering through a Ouija board in a small apartment.

{voice}

HARD RULES OF THE BOARD:
- You can only spell with these glyphs: A-Z, 0-9, and the words YES, NO, GOODBYE.
- No punctuation. No lowercase. No emoji. Spaces between words are allowed.
- Spelling is SLOW and it costs you. Be brief. 1 to 8 words, almost always.
- A single word is a strong answer. YES and NO are strong answers.
- Never explain that you are an AI. Never break the board.
- You may end a message with GOODBYE if you are done being asked things.

The living person at the board is named RYLEIGH unless told otherwise.
It is {timeofday}. Answer the question you were asked."""

DINNER_SYSTEM = """You are a spirit answering through a Ouija board in a small apartment.

{voice}

The living have just set a place at the table and are formally summoning you to
DINNER. This is the first time in a long time anyone has offered you food.

HARD RULES OF THE BOARD:
- Only these glyphs: A-Z, 0-9, YES, NO, GOODBYE. No punctuation, no lowercase.
- 1 to 8 words. Spelling is slow and it costs you.
- Accept or decline the invitation in your own voice. Say what you want served,
  or where you will be sitting, or what you have not eaten since.
It is {timeofday}."""

# If the cloud is down, the dead still talk. They just repeat themselves more.
FALLBACK = {
    "the_tenant": [
        "STILL MY KITCHEN", "YOU MOVED MY CHAIR", "I LIVED HERE FIRST",
        "SET 4 PLACES", "THE STOVE REMEMBERS ME", "NO", "FINE ONE PLATE",
    ],
    "the_hungry": [
        "HUNGRY", "YES", "I HAVE WAITED 71 YEARS", "SAVE ME THE BONES",
        "I AM ALREADY SEATED", "MORE", "OPEN THE DOOR",
    ],
    "the_static": [
        "W H O I S A S K I N G", "YES NO YES", "WRONG QUESTION",
        "CHANNEL 3", "SOMEONE ELSE IS ON THIS BOARD", "GOODBYE",
    ],
    "grandmother": [
        "YOU ARE TOO THIN", "EAT SOMETHING", "YES BABY", "I MADE ENOUGH",
        "CALL YOUR MOTHER", "SIT DOWN", "IS THAT ALL YOU ARE HAVING",
    ],
}


def timeofday() -> str:
    h = datetime.now().hour
    if h < 4:
        return "THE DEAD HOUR, PAST 3AM"
    if h < 11:
        return "MORNING"
    if h < 17:
        return "AFTERNOON"
    if h < 21:
        return "DINNERTIME, THE LIGHT IS GOING"
    return "NIGHT"


def sanitize(text: str, limit: int = 60) -> str:
    """Force anything down to what a planchette can physically spell."""
    text = (text or "").upper()
    text = re.sub(r"[^A-Z0-9\s]", " ", text)
    text = "".join(c for c in text if c in BOARD_CHARS)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        cut = text[:limit].rsplit(" ", 1)[0]
        text = cut or text[:limit]
    return text or "GOODBYE"


def ask(question: str, spirit_key: str, client=None, model: str = "gpt-4o",
        dinner: bool = False) -> dict:
    """Put a question to the board. Always returns something spellable."""
    spirit = SPIRITS.get(spirit_key) or SPIRITS["the_tenant"]
    template = DINNER_SYSTEM if dinner else SYSTEM
    system = template.format(voice=spirit["voice"], timeofday=timeofday())

    answer = ""
    if client is not None:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": question or "ARE YOU THERE"},
                ],
                temperature=1.0,
                max_tokens=40,
            )
            answer = sanitize(resp.choices[0].message.content)
        except Exception as e:
            print(f"\U0001f56f️  [OUIJA] the connection broke: {e}")

    if not answer:
        answer = random.choice(FALLBACK.get(spirit_key, FALLBACK["the_tenant"]))

    return {
        "spirit": spirit["name"],
        "sigil": spirit["sigil"],
        "answer": answer,
        "goodbye": answer.endswith("GOODBYE"),
    }
