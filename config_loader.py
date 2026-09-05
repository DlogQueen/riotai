"""Shared config loader to avoid circular imports"""
import json
import os
from pathlib import Path

_config = None

def get_config():
    global _config
    if _config is None:
        with open(Path(__file__).parent / 'config.json') as f:
            _config = json.load(f)
        if os.environ.get('OPENAI_API_KEY'):
            _config['models']['cloud']['api_key'] = os.environ['OPENAI_API_KEY']
        if os.environ.get('GROQ_API_KEY'):
            _config['models']['groq']['api_key'] = os.environ['GROQ_API_KEY']
        if os.environ.get('GROQ_MODEL'):
            _config['models']['groq']['model'] = os.environ['GROQ_MODEL']
    return _config
