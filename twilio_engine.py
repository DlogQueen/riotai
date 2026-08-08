"""
COACH BEAR AI - Twilio Integration
Coach's Hotline: he calls you, you call him, he texts you.
"""

import os
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI

ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')

COACH_VOICE = 'Polly.Matthew'


def get_twilio():
    return Client(ACCOUNT_SID, AUTH_TOKEN)


def call_user(to_number: str, message: str, voice: str = COACH_VOICE) -> dict:
    """Coach calls you and speaks a message"""
    try:
        client = get_twilio()

        # Build TwiML - speak the message then hang up
        resp = VoiceResponse()
        resp.say(message, voice=voice)

        call = client.calls.create(
            to=to_number,
            from_=TWILIO_NUMBER,
            twiml=str(resp)
        )
        print(f"📞 [TWILIO] Calling {to_number} - SID: {call.sid}")
        return {'success': True, 'sid': call.sid}
    except Exception as e:
        print(f"❌ [TWILIO] Call failed: {e}")
        return {'success': False, 'error': str(e)}


def send_sms(to_number: str, message: str) -> dict:
    """Send SMS from Coach"""
    try:
        client = get_twilio()
        msg = client.messages.create(
            to=to_number,
            from_=TWILIO_NUMBER,
            body=message[:1600]
        )
        print(f"💬 [TWILIO] SMS sent to {to_number} - SID: {msg.sid}")
        return {'success': True, 'sid': msg.sid}
    except Exception as e:
        print(f"❌ [TWILIO] SMS failed: {e}")
        return {'success': False, 'error': str(e)}


def handle_incoming_call(base_url: str) -> str:
    """TwiML for when someone calls the Twilio number - connects to Coach"""
    resp = VoiceResponse()

    greeting = ("This is Bear Bryant. Whoever set this line up, I don't fully understand it, "
                "but I reckon I've got a minute. What's on your mind, son?")

    gather = Gather(
        input='speech',
        action=f'{base_url}/api/twilio/respond',
        method='POST',
        speech_timeout='auto',
        language='en-US'
    )
    gather.say(greeting, voice=COACH_VOICE)
    resp.append(gather)

    # If no input
    resp.say("Didn't catch that. Call back when you're ready to talk.", voice=COACH_VOICE)

    return str(resp)


def handle_voice_response(speech_input: str, api_key: str, base_url: str) -> str:
    """Process speech input and respond via TwiML, in character as Coach"""
    try:
        from memory import build_memory_context
        from config_loader import get_config

        config = get_config()
        persona = config['personas'][config['settings']['default_persona']]
        system_prompt = persona['system_prompt']
        memory_ctx = build_memory_context()
        if memory_ctx:
            system_prompt += f"\n\nCOACH'S NOTEBOOK:\n{memory_ctx}"

        # Add phone context
        system_prompt += "\n\nYou are on a PHONE CALL. Keep responses SHORT (2-3 sentences max). Speak naturally."

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': speech_input}
            ],
            max_tokens=150,
            temperature=0.85
        )
        ai_reply = response.choices[0].message.content.strip()

        # Build TwiML response
        resp = VoiceResponse()

        gather = Gather(
            input='speech',
            action=f'{base_url}/api/twilio/respond',
            method='POST',
            speech_timeout='auto',
            language='en-US'
        )
        gather.say(ai_reply, voice=COACH_VOICE)
        resp.append(gather)
        resp.say("Alright, that's all I've got for now. Go get your work done.", voice=COACH_VOICE)

        return str(resp)

    except Exception:
        resp = VoiceResponse()
        resp.say("Something's gone sideways on this line. Call back later.", voice=COACH_VOICE)
        return str(resp)
