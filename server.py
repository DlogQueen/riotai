#!/usr/bin/env python3
"""
RIOT AI - Break rules. Build empires. Stay punk.
"""

import json
import os
import requests
import base64
import tempfile
from pathlib import Path
from datetime import datetime
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

from database import (
    save_message, get_recent_messages, get_history,
    clear_history, count_messages
)
from memory import (
    build_memory_context, save_memory, save_fact,
    extract_facts_from_message, save_session_summary, get_all_memories
)

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"

with open(CONFIG_FILE) as f:
    config = json.load(f)

# Override with env vars if present (production)
if os.environ.get('OPENAI_API_KEY'):
    config['models']['cloud']['api_key'] = os.environ['OPENAI_API_KEY']
if os.environ.get('OPENAI_MODEL'):
    config['models']['cloud']['model'] = os.environ['OPENAI_MODEL']
if os.environ.get('GROQ_API_KEY'):
    config['models']['groq']['api_key'] = os.environ['GROQ_API_KEY']
if os.environ.get('GROQ_MODEL'):
    config['models']['groq']['model'] = os.environ['GROQ_MODEL']

# Fall back to whatever actually has a key, so a missing GROQ_API_KEY degrades
# to OpenAI instead of failing every request.
_default = config['settings']['default_model']
if not str(config['models'][_default].get('api_key', '')).startswith(('sk-', 'gsk_')):
    for _alt in ('groq', 'cloud', 'local'):
        if str(config['models'].get(_alt, {}).get('api_key', '')).startswith(('sk-', 'gsk_')):
            print(f"[MODEL] {_default} has no key, falling back to {_alt}")
            config['settings']['default_model'] = _alt
            break

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'riot-dev-secret-change-me-in-prod'

# RAW - the real-life social network, mounted at /real
try:
    from real_routes import real as real_blueprint
    app.register_blueprint(real_blueprint)
    print("🫀 [RAW] Real-life social network mounted at /real")
except Exception as e:
    print(f"⚠️  RAW social network not loaded: {e}")

voice_engine = VoiceEngine(config['models']['cloud']['api_key']) if VOICE_VISION_AVAILABLE else None
vision_engine = VisionEngine(config['models']['cloud']['api_key']) if VOICE_VISION_AVAILABLE else None
emotion_detector = EmotionDetector() if EMOTION_AVAILABLE else None

print("=" * 60)
print("🖤 RIOT AI - PUNK MODE ACTIVATED")
print("🦇 Raven + 💀 Riot are ready")
print("🧠 Memory engine online")
print("=" * 60)


def get_client(model_key='cloud'):
    m = config['models'][model_key]
    return OpenAI(base_url=m['base_url'], api_key=m['api_key'])


# ── Memory tools Raven/Riot can call themselves ────────────────────────────────

MEMORY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save something important to long-term memory. Use this when you learn something meaningful about your partner or want to remember something for future conversations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short label for this memory (e.g. 'favorite_band', 'birthday', 'current_project')"},
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
            "description": "Look up what you remember about your partner. Use when you want to check what you know.",
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
            "description": "Save a specific fact you learned about your partner.",
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
    """Execute a memory tool call from the AI"""
    if tool_name == "save_memory":
        save_memory(
            key=tool_args['key'],
            value=tool_args['value'],
            category=tool_args.get('category', 'general'),
            importance=tool_args.get('importance', 5)
        )
        print(f"🧠 [MEMORY] Saved: {tool_args['key']} = {tool_args['value'][:50]}")
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
        print(f"🧠 [MEMORY] Fact saved: [{tool_args['category']}] {tool_args['fact']}")
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
    import threading
    threading.Thread(target=extract_facts_from_message, args=(user_message, api_key), daemon=True).start()

    def generate():
        base_prompt = config['personas'][persona_key]['system_prompt']
        memory_ctx = build_memory_context()
        if memory_ctx:
            system_prompt = base_prompt + f"\n\n{'='*40}\nYOUR MEMORY BANK:\n{memory_ctx}\n{'='*40}\nUse this to personalize your responses."
        else:
            system_prompt = base_prompt + "\n\nYou have no memories yet - pay attention and remember things about your partner."

        messages = [{'role': 'system', 'content': system_prompt}]
        for msg in get_recent_messages(20):
            messages.append(msg)

        try:
            client = get_client(model_key)
            model_cfg = config['models'][model_key]

            # Tool support is declared per model in config.json (local models
            # and some hosted ones do not implement tool calling).
            use_tools = bool(model_cfg.get('supports_tools'))

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
        persona = request.json.get('persona', 'raven')
        if not text:
            return jsonify({'success': False, 'error': 'No text'})
        voice = 'nova' if persona == 'raven' else 'echo'
        client = get_client('cloud')
        response = client.audio.speech.create(model="tts-1", voice=voice, input=text[:500])
        tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        response.stream_to_file(tmp.name)
        tmp.close()
        return send_file(tmp.name, mimetype='audio/mpeg', as_attachment=False)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ── VISION ─────────────────────────────────────────────────────────────────────

@app.route('/api/vision/analyze', methods=['POST'])
def vision_analyze():
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image'})
        file = request.files['image']
        prompt = request.form.get('prompt', "What's in this image?")
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
            max_tokens=500
        )
        return jsonify({'success': True, 'analysis': response.choices[0].message.content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ── EMOTION ────────────────────────────────────────────────────────────────────

@app.route('/api/emotion/detect', methods=['POST'])
def emotion_detect():
    try:
        text = request.json.get('text', '')
        if emotion_detector:
            result = emotion_detector.detect_text_emotion(text)
        else:
            lower = text.lower()
            if any(w in lower for w in ['happy', 'great', 'awesome', 'sick', 'dope']):
                result = {'success': True, 'emotion': 'happy', 'confidence': 0.7, 'polarity': 0.5}
            elif any(w in lower for w in ['sad', 'down', 'bummed']):
                result = {'success': True, 'emotion': 'sad', 'confidence': 0.7, 'polarity': -0.5}
            elif any(w in lower for w in ['angry', 'pissed', 'mad']):
                result = {'success': True, 'emotion': 'angry', 'confidence': 0.7, 'polarity': -0.7}
            else:
                result = {'success': True, 'emotion': 'neutral', 'confidence': 0.6, 'polarity': 0.0}
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ── N8N MCP ────────────────────────────────────────────────────────────────────

@app.route('/api/n8n/tools', methods=['GET'])
def n8n_list_tools():
    try:
        url = os.environ.get('N8N_MCP_URL', config.get('n8n', {}).get('mcp_server_url', ''))
        token = os.environ.get('N8N_MCP_TOKEN', config.get('n8n', {}).get('mcp_token', ''))
        headers = {'Authorization': f"Bearer {token}", 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers,
                             json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, timeout=10)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/n8n/call', methods=['POST'])
def n8n_call_tool():
    try:
        data = request.json
        url = os.environ.get('N8N_MCP_URL', config.get('n8n', {}).get('mcp_server_url', ''))
        token = os.environ.get('N8N_MCP_TOKEN', config.get('n8n', {}).get('mcp_token', ''))
        headers = {'Authorization': f"Bearer {token}", 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers,
                             json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                   "params": {"name": data.get('tool'), "arguments": data.get('args', {})}}, timeout=30)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)})


# ── TWILIO ─────────────────────────────────────────────────────────────────────

@app.route('/api/twilio/call', methods=['POST'])
def twilio_call():
    """Raven calls your phone"""
    if not TWILIO_AVAILABLE:
        return jsonify({'success': False, 'error': 'Twilio not installed'})
    data = request.json
    to_number = data.get('to')
    message = data.get('message', "Hey, it's Raven. Just checking in. Stay punk. 🖤")
    if not to_number:
        return jsonify({'success': False, 'error': 'No phone number provided'})
    result = call_user(to_number, message)
    return jsonify(result)


@app.route('/api/twilio/sms', methods=['POST'])
def twilio_sms():
    """Raven texts your phone"""
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
    """Webhook - someone calls the Twilio number"""
    persona = request.args.get('persona', 'raven')
    base_url = request.url_root.rstrip('/')
    twiml = handle_incoming_call(base_url, persona)
    return Response(twiml, mimetype='text/xml')


@app.route('/api/twilio/respond', methods=['POST'])
def twilio_respond():
    """Webhook - process speech and respond"""
    speech = request.form.get('SpeechResult', '')
    persona = request.args.get('persona', 'raven')
    base_url = request.url_root.rstrip('/')
    api_key = config['models']['cloud']['api_key']
    twiml = handle_voice_response(speech, persona, api_key, base_url)
    return Response(twiml, mimetype='text/xml')


if __name__ == '__main__':
    print("🚀 Starting on http://localhost:5001")
    print("🖤 Break rules. Build empires. Stay punk. ⚡")
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
