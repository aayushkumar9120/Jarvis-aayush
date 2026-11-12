"""Per-user assistant settings + dynamic LLM endpoint switching."""
import json
import os

import streamlit as st
from openai import OpenAI

SETTINGS_FILE = "user_settings.json"

ENDPOINTS = {
    "Groq": {
        "base_url": "https://api.groq.com/openai/v1", "env": "GROQ_API_KEY",
        "models": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile",
                   "llama-3.1-8b-instant", "meta-llama/llama-4-scout-17b-16e-instruct"],
        "vision_model": "meta-llama/llama-4-scout-17b-16e-instruct",
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1", "env": "OPENAI_API_KEY",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"], "vision_model": "gpt-4o-mini",
    },
    "Ollama (local)": {
        "base_url": "http://localhost:11434/v1", "env": None, "key": "ollama",
        "models": ["llama3.2", "qwen2.5", "mistral"], "vision_model": "llava",
    },
    "Custom": {"base_url": "", "env": "CUSTOM_LLM_API_KEY", "models": [], "vision_model": ""},
}

DEFAULTS = {
    "theme": "Cyberpunk Neon",
    "endpoint": "Groq", "model": "openai/gpt-oss-120b", "custom_model": "",
    "custom_base_url": "", "temperature": 0.2, "memory_window": 12,
    "web_search": True, "long_term_recall": True,
    "tts_enabled": True, "tts_engine": "Browser (online)", "tts_rate": 1.0, "tts_pitch": 1.0,
    "tts_volume": 1.0, "tts_voice_pref": "Auto", "tts_voice_name": "",
    "wake_word": False, "wake_phrase": "hey jarvis", "stt_lang": "en-IN",
    "auto_refresh": False,
}
TTS_ENGINES = ["Browser (online)", "Offline (pyttsx3)", "Off"]
VOICE_PREFS = ["Auto", "Female", "Male", "British", "Indian English"]


def resolve_secret(env_name, fallback=""):
    """env var -> st.secrets -> fallback. Keeps API keys out of source code."""
    if not env_name:
        return fallback
    val = os.environ.get(env_name)
    if val:
        return val
    try:
        return st.secrets.get(env_name, fallback)
    except Exception:
        return fallback


def _load_all():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_user_settings(username):
    s = dict(DEFAULTS)
    s.update(_load_all().get(username, {}))
    return s


def save_user_settings(username, settings):
    data = _load_all()
    data[username] = settings
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def init_settings(username):
    """Call once after login: loads saved settings and seeds widget keys."""
    s = load_user_settings(username)
    st.session_state.settings = s
    for k, v in s.items():
        st.session_state[f"set_{k}"] = v


def get_settings():
    return st.session_state.get("settings", dict(DEFAULTS))


def active_model(s=None):
    s = s or get_settings()
    if s["endpoint"] == "Custom" or s.get("custom_model"):
        return s.get("custom_model") or s["model"]
    return s["model"]


def vision_model(s=None):
    s = s or get_settings()
    return ENDPOINTS.get(s["endpoint"], {}).get("vision_model") or active_model(s)


@st.cache_resource(show_spinner=False)
def _client(base_url, api_key):
    return OpenAI(base_url=base_url, api_key=api_key or "none")


def get_client(settings=None, groq_fallback_key=""):
    s = settings or get_settings()
    ep = ENDPOINTS.get(s["endpoint"], ENDPOINTS["Groq"])
    base = s.get("custom_base_url") if s["endpoint"] == "Custom" else ep["base_url"]
    key = ep.get("key") or resolve_secret(ep["env"], groq_fallback_key if s["endpoint"] == "Groq" else "")
    return _client(base or ENDPOINTS["Groq"]["base_url"], key)


def get_groq_client(groq_fallback_key=""):
    """Speech-to-text always goes through Groq Whisper."""
    return _client(ENDPOINTS["Groq"]["base_url"], resolve_secret("GROQ_API_KEY", groq_fallback_key))
