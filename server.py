#!/usr/bin/env python3
"""
COACH BEAR AI
A declassified-black-project bit: chat, voice, and a phone hotline with an AI
tribute to Paul "Bear" Bryant. Parody/fan project — see persona/bear_system_prompt.md
and the disclaimer in config.json for the (fictional) lore and the real disclaimer.
"""

import json
import os
import base64
import threading
import tempfile
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, send_file
from openai import OpenAI

# Load .env for local dev
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

try:
    from twilio_engine import call_user, send_sms, handle_incoming_call, handle_voice_response
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("⚠️  Twilio not installed: pip install twilio")

try:
    from voice_vision import VoiceEngine, VisionEngine
    VOICE_VISION_AVAILABLE = True
except ImportError:
    VOICE_VISION_AVAILABLE = False

try:
    from emotion_engine import EmotionDetector
    EMOTION_AVAILABLE = True
except ImportError:
    EMOTION_AVAILABLE = False

from config_loader import get_config
from sports_engine import get_scoreboard, get_game_snapshot, snapshot_to_text
from database import (
    save_message, get_recent_messages, get_history,
    clear_history, count_messages
)
from memory import (
    build_memory_context, save_memory, save_fact,
    extract_facts_from_message, save_session_summary, get_all_memories
)

BASE_DIR = Path(__file__).parent
config = get_config()

app = Flask(__name__)

voice_engine = VoiceEngine(config['models']['cloud']['api_key']) if VOICE_VISION_AVAILABLE else None
vision_engine = VisionEngine(config['models']['cloud']['api_key']) if VOICE_VISION_AVAILABLE else None
emotion_detector = EmotionDetector() if EMOTION_AVAILABLE else None

print("=" * 60)
print("🏈 COACH BEAR AI - archive online")
print("🎩 Houndstooth mode engaged")
print("📓 Notebook (memory) engine online")
print("=" * 60)


def get_client(model_key='cloud'):
    m = config['models'][model_key]
    return OpenAI(base_url=m['base_url'], api_key=m['api_key'])


def get_persona(persona_key: str) -> dict:
    return config['personas'].get(persona_key, config['personas'][config['settings']['default_persona']])


# ── Notebook tools Coach can call himself ───────────────────────────────────

MEMORY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save something worth remembering about the person you're talking to. Use this when you learn something meaningful that should carry into future conversations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short label for this memory (e.g. 'position', 'hometown', 'goal')"},
                    "value": {"type": "string", "description": "What to remember"},
                    "category": {
                        "type": "string",
                        "enum": ["identity", "preferences", "work", "relationships", "goals", "emotions", "skills", "history", "general"],
                        "description": "Category for this memory"
                    },
                    "importance": {"type": "integer", "minimum": 1, "maximum": 10, "description": "How important is this? 1=trivial, 10=critical"}
                },
                "required": ["key", "value", "category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memories",
            "description": "Look up what's in the notebook about the person you're talking to.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Optional category to filter by"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_fact",
            "description": "Save a specific fact you learned about the person you're talking to.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Category: identity, preferences, work, relationships, goals, emotions, skills, history"},
                    "fact": {"type": "string", "description": "The fact to remember"}
                },
                "required": ["category", "fact"]
            }
        }
    }
]


def handle_tool_call(tool_name: str, tool_args: dict) -> str:
    """Execute a notebook (memory) tool call from Coach"""
    if tool_name == "save_memory":
        save_memory(
            key=tool_args['key'],
            value=tool_args['value'],
            category=tool_args.get('category', 'general'),
            importance=tool_args.get('importance', 5)
        )
        print(f"📓 [NOTEBOOK] Saved: {tool_args['key']} = {tool_args['value'][:50]}")
        return f"Memory saved: {tool_args['key']}"

    elif tool_name == "recall_memories":
        mem = get_all_memories()
        result = []
        cat_filter = tool_args.get('category')
        if mem['facts']:
            for cat, facts in mem['facts'].items():
                if not cat_filter or cat == cat_filter:
                    result.append(f"[{cat}]: " + ", ".join(facts[:5]))
        if mem['named']:
            for m in mem['named'][:10]:
                if not cat_filter or m['category'] == cat_filter:
                    result.append(f"{m['key']}: {m['value']}")
        return '\n'.join(result) if result else "No memories found."

    elif tool_name == "save_fact":
        save_fact(tool_args['category'], tool_args['fact'])
        print(f"📓 [NOTEBOOK] Fact saved: [{tool_args['category']}] {tool_args['fact']}")
        return f"Fact saved: {tool_args['fact']}"

    return "Unknown tool"


@app.route('/')
def index():
    return render_template('index.html', config=config)


@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    data = request.json
    user_message = data.get('message', '')
    persona_key = data.get('persona', config['settings']['default_persona'])
    model_key = data.get('model', config['settings']['default_model'])
    emotion = data.get('emotion', 'neutral')

    if not user_message:
        return jsonify({'error': 'No message'}), 400

    save_message('user', user_message, persona_key, model_key, emotion)

    api_key = config['models']['cloud']['api_key']
    threading.Thread(target=extract_facts_from_message, args=(user_message, api_key), daemon=True).start()

    def generate():
        base_prompt = get_persona(persona_key)['system_prompt']
        memory_ctx = build_memory_context()
        if memory_ctx:
            system_prompt = base_prompt + f"\n\n{'='*40}\nCOACH'S NOTEBOOK ON THIS PERSON:\n{memory_ctx}\n{'='*40}\nUse this to personalize your responses."
        else:
            system_prompt = base_prompt + "\n\nYour notebook is empty so far - pay attention and remember things worth carrying forward."

        messages = [{'role': 'system', 'content': system_prompt}]
        for msg in get_recent_messages(20):
            messages.append(msg)

        try:
            client = get_client(model_key)
            model_cfg = config['models'][model_key]

            # Hosted models (OpenAI, OpenRouter) support tool calling; small local
            # models generally don't, so skip tools there.
            use_tools = model_key != 'local'

            if use_tools:
                # Non-streaming first pass to handle tool calls
                response = client.chat.completions.create(
                    model=model_cfg['model'],
                    messages=messages,
                    temperature=config['settings']['temperature'],
                    max_tokens=config['settings']['max_tokens'],
                    tools=MEMORY_TOOLS,
                    tool_choice="auto"
                )

                msg = response.choices[0].message

                # Handle any tool calls silently
                if msg.tool_calls:
                    tool_results = []
                    for tc in msg.tool_calls:
                        args = json.loads(tc.function.arguments)
                        result = handle_tool_call(tc.function.name, args)
                        tool_results.append({
                            "tool_call_id": tc.id,
                            "role": "tool",
                            "content": result
                        })
                        # Signal UI that a memory was saved
                        if tc.function.name in ('save_memory', 'save_fact'):
                            yield f"data: {json.dumps({'memory_saved': True, 'key': args.get('key', args.get('fact', ''))[:40]})}\n\n"

                    # Continue with tool results, now stream the final response
                    messages.append(msg)
                    messages.extend(tool_results)

                    stream = client.chat.completions.create(
                        model=model_cfg['model'],
                        messages=messages,
                        temperature=config['settings']['temperature'],
                        max_tokens=config['settings']['max_tokens'],
                        stream=True
                    )
                else:
                    # No tool calls - stream the response we already have, then re-stream
                    stream = client.chat.completions.create(
                        model=model_cfg['model'],
                        messages=messages,
                        temperature=config['settings']['temperature'],
                        max_tokens=config['settings']['max_tokens'],
                        stream=True
                    )
            else:
                # Local model - just stream directly
                stream = client.chat.completions.create(
                    model=model_cfg['model'],
                    messages=messages,
                    temperature=config['settings']['temperature'],
                    max_tokens=config['settings']['max_tokens'],
                    stream=True
                )

            full_response = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    piece = chunk.choices[0].delta.content
                    full_response += piece
                    yield f"data: {json.dumps({'content': piece})}\n\n"

            save_message('assistant', full_response, persona_key, model_key, emotion)
            yield f"data: {json.dumps({'done': True})}\n\n"

            # Summarize every 20 messages
            count = count_messages()
            if count % 20 == 0:
                recent = get_recent_messages(20)
                threading.Thread(target=save_session_summary, args=(recent, persona_key, api_key), daemon=True).start()

        except Exception as e:
            import traceback
            print(f"❌ [CHAT] Error: {e}")
            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/history', methods=['GET'])
def get_history_route():
    return jsonify(get_history(100))


@app.route('/api/history/clear', methods=['POST'])
def clear_history_route():
    clear_history()
    return jsonify({'success': True})


@app.route('/api/memory', methods=['GET'])
def get_memory_api():
    mem = get_all_memories()
    return jsonify(mem)


@app.route('/api/memory', methods=['POST'])
def save_memory_api():
    data = request.json
    save_memory(data['key'], data['value'], data.get('category', 'general'), data.get('importance', 5))
    return jsonify({'success': True})


@app.route('/api/memory/facts', methods=['GET'])
def get_facts():
    mem = get_all_memories()
    return jsonify(mem['facts'])


# ── VOICE ──────────────────────────────────────────────────────────────────────

@app.route('/api/voice/transcribe', methods=['POST'])
def voice_transcribe():
    try:
        if 'audio' not in request.files:
            return jsonify({'success': False, 'error': 'No audio file'})
        audio_file = request.files['audio']
        tmp = tempfile.NamedTemporaryFile(suffix='.webm', delete=False)
        audio_file.save(tmp.name)
        tmp.close()
        client = get_client('cloud')
        with open(tmp.name, 'rb') as f:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=f, language="en")
        os.unlink(tmp.name)
        return jsonify({'success': True, 'text': transcript.text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/voice/speak', methods=['POST'])
def voice_speak():
    try:
        text = request.json.get('text', '')
        persona_key = request.json.get('persona', config['settings']['default_persona'])
        if not text:
            return jsonify({'success': False, 'error': 'No text'})
        voice = get_persona(persona_key).get('voice', 'onyx')
        client = get_client('cloud')
        response = client.audio.speech.create(model="tts-1", voice=voice, input=text[:500])
        tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        response.stream_to_file(tmp.name)
        tmp.close()
        return send_file(tmp.name, mimetype='audio/mpeg', as_attachment=False)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ── FILM (VISION) ────────────────────────────────────────────────────────────

@app.route('/api/vision/analyze', methods=['POST'])
def vision_analyze():
    """Show Coach a photo - the playbook, the film, whatever's on your mind."""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image'})
        file = request.files['image']
        prompt = request.form.get(
            'prompt',
            "You are Coach Bear Bryant looking at film someone just showed you. React to it in character - short, plainspoken, coach-like."
        )
        image_path = BASE_DIR / 'temp_image.jpg'
        file.save(image_path)
        client = get_client('cloud')
        with open(image_path, 'rb') as img:
            image_data = base64.b64encode(img.read()).decode('utf-8')
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
            ]}],
            max_tokens=400
        )
        return jsonify({'success': True, 'analysis': response.choices[0].message.content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ── READ THE ROOM (EMOTION) ─────────────────────────────────────────────────

@app.route('/api/emotion/detect', methods=['POST'])
def emotion_detect():
    try:
        text = request.json.get('text', '')
        if emotion_detector:
            result = emotion_detector.detect_text_emotion(text)
        else:
            lower = text.lower()
            if any(w in lower for w in ['happy', 'great', 'awesome', 'pumped', 'fired up']):
                result = {'success': True, 'emotion': 'happy', 'confidence': 0.7, 'polarity': 0.5}
            elif any(w in lower for w in ['sad', 'down', 'discouraged']):
                result = {'success': True, 'emotion': 'sad', 'confidence': 0.7, 'polarity': -0.5}
            elif any(w in lower for w in ['angry', 'pissed', 'mad', 'frustrated']):
                result = {'success': True, 'emotion': 'angry', 'confidence': 0.7, 'polarity': -0.7}
            else:
                result = {'success': True, 'emotion': 'neutral', 'confidence': 0.6, 'polarity': 0.0}
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ── COACH'S SPORTS TALK (LIVE COLLEGE FOOTBALL) ─────────────────────────────

@app.route('/api/sports/scoreboard', methods=['GET'])
def sports_scoreboard():
    """Live/upcoming/recent college football games, straight from ESPN's public feed."""
    team = request.args.get('team', '').strip() or None
    games = get_scoreboard(team=team)
    return jsonify({'success': True, 'games': games})


@app.route('/api/sports/game/<event_id>', methods=['GET'])
def sports_game(event_id):
    """Detailed live snapshot for one game (score, situation, recent plays)."""
    snap = get_game_snapshot(event_id)
    if not snap:
        return jsonify({'success': False, 'error': 'Could not load that game'})
    return jsonify({'success': True, 'game': snap, 'text': snapshot_to_text(snap)})


@app.route('/api/sports/talk', methods=['POST'])
def sports_talk():
    """
    Coach goes 'on air': feeds a real, live game snapshot into the persona
    and gets back a short talk-show / play-by-play reaction grounded in the
    actual current score and situation.
    """
    data = request.json or {}
    event_id = data.get('event_id')
    if not event_id:
        return jsonify({'success': False, 'error': 'No event_id provided'})

    snap = get_game_snapshot(event_id)
    if not snap:
        return jsonify({'success': False, 'error': 'Could not load that game right now'})

    game_text = snapshot_to_text(snap)
    persona_key = data.get('persona', config['settings']['default_persona'])
    base_prompt = get_persona(persona_key)['system_prompt']

    broadcast_prompt = (
        base_prompt
        + "\n\n" + "=" * 40
        + "\nYOU ARE LIVE ON AIR, hosting a sports-talk segment. Below is REAL, CURRENT data "
          "for a real college football game pulled just now. React to it in character - call "
          "the action, give your read on the situation, maybe a prediction. 2-5 sentences, "
          "energetic, like a radio call. Do not invent plays, players, or numbers beyond what's "
          "given below.\n\n" + game_text + "\n" + "=" * 40
    )

    try:
        client = get_client('cloud')
        model_cfg = config['models']['cloud']
        response = client.chat.completions.create(
            model=model_cfg['model'],
            messages=[{'role': 'system', 'content': broadcast_prompt},
                      {'role': 'user', 'content': "Give the crowd your call of the game right now."}],
            temperature=0.9,
            max_tokens=300,
        )
        commentary = response.choices[0].message.content.strip()
        return jsonify({'success': True, 'commentary': commentary, 'game': snap})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ── COACH'S HOTLINE (TWILIO) ────────────────────────────────────────────────

@app.route('/api/twilio/call', methods=['POST'])
def twilio_call():
    """Coach calls your phone"""
    if not TWILIO_AVAILABLE:
        return jsonify({'success': False, 'error': 'Twilio not installed'})
    data = request.json
    to_number = data.get('to')
    message = data.get('message', "This is Coach Bryant. Just checking in. Get after it today, hear?")
    if not to_number:
        return jsonify({'success': False, 'error': 'No phone number provided'})
    result = call_user(to_number, message)
    return jsonify(result)


@app.route('/api/twilio/sms', methods=['POST'])
def twilio_sms():
    """Coach texts your phone"""
    if not TWILIO_AVAILABLE:
        return jsonify({'success': False, 'error': 'Twilio not installed'})
    data = request.json
    to_number = data.get('to')
    message = data.get('message', '')
    if not to_number or not message:
        return jsonify({'success': False, 'error': 'Missing to or message'})
    result = send_sms(to_number, message)
    return jsonify(result)


@app.route('/api/twilio/incoming', methods=['POST'])
def twilio_incoming():
    """Webhook - someone calls the Twilio number and gets Coach"""
    base_url = request.url_root.rstrip('/')
    twiml = handle_incoming_call(base_url)
    return Response(twiml, mimetype='text/xml')


@app.route('/api/twilio/respond', methods=['POST'])
def twilio_respond():
    """Webhook - process speech and respond as Coach"""
    speech = request.form.get('SpeechResult', '')
    base_url = request.url_root.rstrip('/')
    api_key = config['models']['cloud']['api_key']
    twiml = handle_voice_response(speech, api_key, base_url)
    return Response(twiml, mimetype='text/xml')


if __name__ == '__main__':
    print("🚀 Starting on http://localhost:5001")
    print("🏈 Coach Bear AI is up. Bring your notebook. ⚡")
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
