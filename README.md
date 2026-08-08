# 🏈 Coach Bear AI

A fun, fictional AI tribute to Paul "Bear" Bryant — the winningest coach in
college football history until the late '90s, six national championships at
Alabama, houndstooth hat, gravelly Arkansas drawl. He died in 1983.

The app's in-universe conceit: a declassified government research project
supposedly captured his neural patterns in his final days, and the tech to
actually run that pattern just now caught up. It's a wink, not a hoax — the
app is upfront (in the UI and if you ask Coach directly) that this is an AI
tribute built from his real quotes, biography, and coaching philosophy, not
the man himself. **Not affiliated with the Bryant family, the University of
Alabama, or any real government program.**

## What it does

- **💬 Chat** — talk with an AI playing Coach Bryant, in character, with real
  biographical knowledge (his career, his players, his quotes) and an honest
  sense of what he wouldn't actually know about the decades since 1983.
- **🎤 Voice in, 🔊 voice out** — record a question with your mic (Whisper
  transcription) and have Coach's replies read back in a deep, gravelly
  voice (OpenAI TTS).
- **🎙️ Sports Talk** — pulls **real, live college football data** from
  ESPN's public scoreboard/summary feed (no API key needed) and has Coach
  call the game like a talk-radio host, grounded in the actual score and
  situation. "Go on air" to have him auto-update every 25 seconds while a
  game is live.
- **☎️ Coach's Hotline** — optional Twilio integration so Coach can call or
  text your phone.
- **📓 Coach's Notebook** — persistent memory. Coach remembers things about
  you across conversations (position, goals, whatever comes up).

## Quick start

```bash
cp .env.example .env   # add your OPENAI_API_KEY
./START.sh             # or: pip install -r requirements.txt && python3 server.py
```

Then open http://localhost:5001.

Only `OPENAI_API_KEY` is required (it powers chat, voice transcription/TTS,
and image analysis). Everything else in `.env.example` is optional:

| Var | Enables |
|---|---|
| `OPENAI_API_KEY` | Chat, voice (STT/TTS), vision. **Required.** |
| `OPENROUTER_API_KEY` | Swap the chat model to anything on [OpenRouter](https://openrouter.ai) (Claude, Llama, Gemini, ...) — set `settings.default_model` to `"openrouter"` in `config.json`. Voice/vision still need the OpenAI key above. |
| `SUPABASE_URL` / `SUPABASE_KEY` | Persistent memory in Supabase instead of local SQLite (see `supabase_schema.sql`). |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` | Coach's Hotline (calls/texts). |

## How it's put together

```
server.py              Flask app, all API routes
config.json             App branding + persona + model settings
config_loader.py        Loads config.json, resolves persona system prompts, applies env overrides
persona/
  bear_system_prompt.md The actual "who is Coach Bryant" prompt - biography, voice, philosophy
database.py              SQLite (local) / Supabase (prod) storage for chat history + memory
memory.py                "Coach's Notebook" - long-term memory extraction/recall
voice_vision.py           STT/TTS (Whisper, OpenAI TTS) + image analysis helpers
emotion_engine.py         Lightweight sentiment detection ("read the room")
sports_engine.py          Live college football data from ESPN's public scoreboard/summary feed
twilio_engine.py          Coach's Hotline (phone calls + SMS)
templates/index.html      The whole front end (single page, houndstooth/crimson theme)
```

### The persona

`persona/bear_system_prompt.md` is the actual character sheet - his real
biography (Fordyce, Arkansas → Alabama playing days → Maryland → Kentucky →
Texas A&M → Alabama, 1958-1982 → died Jan 26, 1983, 28 days after his last
game), his real quotes, his coaching philosophy, and explicit instructions
for how he should talk about the decades of football he "missed" (playoff
expansion, conference realignment, NIL, the transfer portal, Nick Saban's
run at Alabama) - giving opinions in character rather than inventing facts
he'd have no way to know.

### Live sports data

`sports_engine.py` calls ESPN's public, unauthenticated scoreboard/summary
JSON feed (the same one their own site widgets use - no scraping, no key).
It's a personal-project use of a public endpoint, not an official
integration, so if ESPN ever changes or rate-limits it, calls fail
gracefully rather than crashing the app. If you want a more durable, keyed
data source instead, [CollegeFootballData.com](https://collegefootballdata.com)
(free tier, `/plays` endpoint) is a solid drop-in replacement - swap it in
inside `sports_engine.py` behind the same `get_scoreboard` / `get_game_snapshot`
functions the rest of the app calls.

## Deploying

`vercel.json` is set up for Vercel's Python runtime. Add the env vars from
the table above directly in your Vercel project's **Settings → Environment
Variables** (not via `vercel.json` - the old `"env": {"KEY": "@secret"}`
alias syntax requires pre-creating secrets with `vercel secrets add` and
just breaks the deploy otherwise). For anything longer-lived than local dev,
set `SUPABASE_URL`/`SUPABASE_KEY` so memory survives across deploys (local
SQLite doesn't persist on most serverless platforms).

## Disclaimer

This is a parody/fan-tribute project made for fun. It is not endorsed by,
affiliated with, or officially connected to the Bryant family, the
University of Alabama, the SEC, ESPN, or any real government program - the
"declassified brain-scan project" is fictional lore for an AI chatbot, not a
real claim.
