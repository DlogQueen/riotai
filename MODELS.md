# Model providers

RIOT AI talks to every provider through the OpenAI-compatible client, so adding
one is a config entry, not code. They live under `models` in `config.json`.

| Key | Provider | Default model | Tools | Key env var |
|---|---|---|---|---|
| `groq` | Groq | `llama-3.3-70b-versatile` | yes | `GROQ_API_KEY` |
| `cloud` | OpenAI | `gpt-4o` | yes | `OPENAI_API_KEY` |
| `local` | Ollama | `tinyllama` | no | none needed |

**Groq is the default.** It is fast and cheap, and its API is OpenAI-compatible,
so the same client, streaming, and tool-calling code paths work unchanged.

```bash
export GROQ_API_KEY=gsk_...          # get one at console.groq.com
export GROQ_MODEL=...                # optional: override the model
python3 server.py
```

## Things worth knowing

- **Missing key degrades, it does not crash.** If the default model has no usable
  key at startup, `server.py` falls back to the first provider that does and says
  so in the log. Set `settings.default_model` in `config.json` to pin one.
- **Tool calling is declared, not guessed.** Each model entry carries
  `supports_tools`; `server.py` reads that instead of checking the model's name,
  so a new provider only needs a config entry to get memory tools.
- **Voice and vision still go to OpenAI.** `/api/voice/*` and `/api/vision/*` call
  `get_client('cloud')` directly, because they need Whisper and TTS. Groq serves
  Whisper but no text-to-speech, so speech output would break if pointed at it.
  Transcription could move to Groq; TTS cannot. Until then those two endpoints
  need `OPENAI_API_KEY` even when chat runs on Groq.
- Set keys as environment variables in your host's settings. They are read at
  startup by both `server.py` and `config_loader.py`.
