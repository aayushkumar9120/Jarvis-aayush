"""Visual layer: glowing dark themes, status pills, HUD cards, typing effect."""
import time
import streamlit as st

PALETTES = {
    # name: bg, surface, border, text, muted, accent, accent2
    "Cyberpunk Neon": dict(bg="#07060d", bg2="#120a24", surface="rgba(24,16,48,.72)", border="rgba(0,229,255,.28)",
                           text="#e8f4ff", muted="#8a93b8", accent="#00e5ff", accent2="#ff2bd6", glow="0,229,255"),
    "Minimal Dark": dict(bg="#0d0f12", bg2="#14171c", surface="rgba(28,32,39,.85)", border="rgba(255,255,255,.10)",
                         text="#e9ecf1", muted="#8b93a1", accent="#7c9cff", accent2="#9aa7c7", glow="124,156,255"),
    "Stark Gold": dict(bg="#0a0806", bg2="#1a110a", surface="rgba(36,24,14,.75)", border="rgba(255,183,0,.30)",
                       text="#fff3e0", muted="#b59a78", accent="#ffb700", accent2="#ff5a36", glow="255,183,0"),
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root{--j-bg:__bg;--j-bg2:__bg2;--j-surface:__surface;--j-border:__border;--j-text:__text;--j-muted:__muted;
--j-accent:__accent;--j-accent2:__accent2;--j-glow:__glow;}
html,body,[data-testid="stAppViewContainer"],.stApp{background:radial-gradient(1200px 600px at 85% -10%,rgba(var(--j-glow),.10),transparent 60%),
 radial-gradient(900px 500px at -10% 110%,rgba(255,43,214,.07),transparent 60%),var(--j-bg)!important;color:var(--j-text);
 font-family:'IBM Plex Sans',system-ui,sans-serif;}
[data-testid="stHeader"]{background:transparent!important}
#MainMenu,footer{visibility:hidden}
h1,h2,h3,h4{font-family:'Chakra Petch',sans-serif!important;letter-spacing:.02em;color:var(--j-text)}
h3{text-shadow:0 0 18px rgba(var(--j-glow),.35)}
.block-container{padding-top:1.6rem;max-width:1100px}
::-webkit-scrollbar{width:8px;height:8px}::-webkit-scrollbar-thumb{background:rgba(var(--j-glow),.35);border-radius:8px}

/* sidebar */
[data-testid="stSidebar"]{background:linear-gradient(180deg,var(--j-bg2),var(--j-bg))!important;border-right:1px solid var(--j-border)}
[data-testid="stSidebar"] .stMarkdown h3{font-size:.95rem;color:var(--j-accent)}
[data-testid="stSidebar"] [data-testid="stExpander"]{border:1px solid var(--j-border);border-radius:12px;background:var(--j-surface)}
.jv-brand{display:flex;align-items:center;gap:.6rem;font-family:'Chakra Petch';font-weight:700;font-size:1.25rem;color:var(--j-text)}
.jv-brand i{width:12px;height:12px;border-radius:50%;background:var(--j-accent);box-shadow:0 0 12px var(--j-accent),0 0 28px rgba(var(--j-glow),.6)}

/* buttons */
.stButton>button,.stDownloadButton>button{border-radius:10px;border:1px solid var(--j-border);background:var(--j-surface);
 color:var(--j-text);transition:all .18s ease;backdrop-filter:blur(6px)}
.stButton>button:hover,.stDownloadButton>button:hover{transform:translateY(-2px);border-color:var(--j-accent);color:var(--j-accent);
 box-shadow:0 6px 18px rgba(var(--j-glow),.28)}
.stButton>button[kind="primary"]{background:linear-gradient(90deg,var(--j-accent),var(--j-accent2));color:#05050a;border:none;font-weight:600}
.st-key-chips .stButton>button{border-radius:999px;font-size:.82rem;padding:.25rem .9rem;white-space:nowrap}

/* chat bubbles */
[data-testid="stChatMessage"]{background:var(--j-surface);border:1px solid var(--j-border);border-radius:16px;padding:.9rem 1.1rem;
 margin-bottom:.7rem;backdrop-filter:blur(8px);box-shadow:0 0 0 1px rgba(255,255,255,.02),0 10px 30px rgba(0,0,0,.35)}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"],[data-testid="chatAvatarIcon-user"]){
 background:linear-gradient(135deg,rgba(var(--j-glow),.16),rgba(255,43,214,.10));border-color:rgba(var(--j-glow),.45);margin-left:9%}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"],[data-testid="chatAvatarIcon-assistant"]){
 border-left:3px solid var(--j-accent);margin-right:6%}
[data-testid="stChatInput"]{border:1px solid var(--j-border);border-radius:14px;background:var(--j-surface)}
[data-testid="stChatInput"]:focus-within{border-color:var(--j-accent);box-shadow:0 0 0 1px var(--j-accent),0 0 24px rgba(var(--j-glow),.30)}
[data-testid="stBottom"]>div{background:transparent!important}

/* inputs, tabs */
.stTextInput input,.stTextArea textarea,.stSelectbox [data-baseweb="select"]>div{background:var(--j-surface)!important;border-color:var(--j-border)!important;color:var(--j-text)!important}
.stTabs [data-baseweb="tab-list"]{gap:.3rem;border-bottom:1px solid var(--j-border)}
.stTabs [aria-selected="true"]{color:var(--j-accent)!important}
hr{border-color:var(--j-border)!important}

/* HUD cards */
.jv-hud{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.7rem;margin:.4rem 0 1rem}
.jv-card{border:1px solid var(--j-border);background:var(--j-surface);border-radius:14px;padding:.65rem .9rem;position:relative;overflow:hidden}
.jv-card:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:linear-gradient(var(--j-accent),var(--j-accent2))}
.jv-card small{color:var(--j-muted);font-size:.72rem;letter-spacing:.06em}
.jv-card div{font-family:'IBM Plex Mono',monospace;font-size:1.02rem;color:var(--j-text);margin-top:.1rem;word-break:break-word}

/* status pill */
.jv-status{display:inline-flex;align-items:center;gap:.55rem;padding:.3rem .85rem;border-radius:999px;border:1px solid var(--j-border);
 background:var(--j-surface);font-size:.85rem;color:var(--j-text)}
.jv-status .dot{width:9px;height:9px;border-radius:50%;background:var(--c,var(--j-accent));box-shadow:0 0 10px var(--c,var(--j-accent));animation:jv-pulse 1.2s infinite}
.jv-dots span{animation:jv-blink 1.4s infinite both;font-weight:700}
.jv-dots span:nth-child(2){animation-delay:.2s}.jv-dots span:nth-child(3){animation-delay:.4s}
@keyframes jv-blink{0%,80%,100%{opacity:.2}40%{opacity:1}}
@keyframes jv-pulse{0%,100%{transform:scale(.8);opacity:.7}50%{transform:scale(1.25);opacity:1}}

/* orb */
.jv-orb-wrap{display:flex;align-items:center;gap:1.2rem;margin:.2rem 0 .8rem}
.jv-orb{width:74px;height:74px;flex:none;border-radius:50%;background:radial-gradient(circle at 35% 30%,#fff 0,var(--j-accent) 22%,var(--j-accent2) 100%);
 box-shadow:0 0 28px rgba(var(--j-glow),.7),inset 0 0 18px rgba(255,255,255,.35);animation:jv-orb 3s infinite ease-in-out}
.jv-orb.listening{animation-duration:.9s;filter:hue-rotate(40deg)}
.jv-orb.thinking{animation:jv-spin 1.6s linear infinite;filter:saturate(1.6)}
.jv-orb.speaking{animation-duration:.6s}
@keyframes jv-orb{0%,100%{transform:scale(.94);box-shadow:0 0 18px rgba(var(--j-glow),.45)}50%{transform:scale(1.06);box-shadow:0 0 48px rgba(var(--j-glow),.9)}}
@keyframes jv-spin{0%{transform:rotate(0) scale(1)}50%{transform:rotate(180deg) scale(1.08)}100%{transform:rotate(360deg) scale(1)}}
.jv-orb-title{font-family:'Chakra Petch';font-size:1.35rem;font-weight:700;color:var(--j-text)}
.jv-orb-sub{color:var(--j-muted);font-size:.9rem}
@media (prefers-reduced-motion:reduce){.jv-orb,.jv-status .dot,.jv-dots span{animation:none!important}}
@media (max-width:640px){[data-testid="stChatMessage"]{margin-left:0!important;margin-right:0!important}.jv-orb{width:56px;height:56px}}
</style>
"""

STATUS = {  # state -> (label, colour)
    "idle": ("Standing by", "#5ee6a8"),
    "listening": ("Jarvis is listening", "#ffd24a"),
    "transcribing": ("Transcribing your voice", "#ffd24a"),
    "thinking": ("Processing request", "#00e5ff"),
    "searching": ("Searching the web", "#7c9cff"),
    "imaging": ("Generating image", "#ff2bd6"),
    "reading": ("Reading file", "#7c9cff"),
    "responding": ("Typing response", "#00e5ff"),
    "speaking": ("Speaking", "#5ee6a8"),
    "error": ("Something went wrong", "#ff5a5a"),
}


def inject_theme(name="Cyberpunk Neon"):
    p = PALETTES.get(name, PALETTES["Cyberpunk Neon"])
    css = _CSS
    for k, v in p.items():
        css = css.replace(f"__{k}", v)
    st.markdown(css, unsafe_allow_html=True)


def status_html(state="idle", text=None):
    label, color = STATUS.get(state, STATUS["idle"])
    animated = state not in ("idle", "error")
    dots = '<span class="jv-dots"><span>.</span><span>.</span><span>.</span></span>' if animated else ""
    return f'<div class="jv-status" style="--c:{color}"><span class="dot"></span>{text or label}{dots}</div>'


def render_status(slot, state="idle", text=None):
    """slot is an st.empty() placeholder - call again later to update it."""
    slot.markdown(status_html(state, text), unsafe_allow_html=True)


def hud_cards(items):
    cards = "".join(f'<div class="jv-card"><small>{k}</small><div>{v}</div></div>' for k, v in items)
    st.markdown(f'<div class="jv-hud">{cards}</div>', unsafe_allow_html=True)


def typing_effect(slot, text, delay=0.008, chunk=3):
    """Types out locally-generated replies (LLM replies stream natively)."""
    shown = ""
    for i in range(0, len(text), chunk):
        shown = text[: i + chunk]
        slot.markdown(shown + " ▌")
        time.sleep(delay)
    slot.markdown(text)
