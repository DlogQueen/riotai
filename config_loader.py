"""Shared config loader to avoid circular imports"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
_config = None


def _load_persona_prompts(config: dict) -> None:
    """Personas can point at a markdown file instead of inlining the prompt in JSON."""
    for persona in config.get('personas', {}).values():
        prompt_file = persona.get('system_prompt_file')
        if prompt_file:
            path = BASE_DIR / prompt_file
            persona['system_prompt'] = path.read_text()


def get_config() -> dict:
    global _config
    if _config is None:
        with open(BASE_DIR / 'config.json') as f:
            _config = json.load(f)
        _load_persona_prompts(_config)
        if os.environ.get('OPENAI_API_KEY'):
            _config['models']['cloud']['api_key'] = os.environ['OPENAI_API_KEY']
        if os.environ.get('OPENAI_MODEL'):
            _config['models']['cloud']['model'] = os.environ['OPENAI_MODEL']
        if os.environ.get('OPENROUTER_API_KEY'):
            _config['models']['openrouter']['api_key'] = os.environ['OPENROUTER_API_KEY']
        if os.environ.get('OPENROUTER_MODEL'):
            _config['models']['openrouter']['model'] = os.environ['OPENROUTER_MODEL']
    return _config
