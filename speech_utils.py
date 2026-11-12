"""Voice in/out: configurable TTS (browser or offline), Groq Whisper STT, wake word."""
import json
import re
import threading

import streamlit as st
import streamlit.components.v1 as components


def clean_for_speech(text, limit=700):
    text = re.sub(r"```.*?```", " code block omitted. ", text or "", flags=re.S)
    text = re.sub(r"https?://\S+", " link ", text)
    text = re.sub(r"[*_`#>|~]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


_VOICE_JS = """
<script>
(function(){
  const text=%(text)s, cfg=%(cfg)s;
  if(!('speechSynthesis' in window)) return;
  const pickVoice=()=>{
    const vs=speechSynthesis.getVoices(); if(!vs.length) return null;
    if(cfg.name){const v=vs.find(v=>v.name.toLowerCase().includes(cfg.name.toLowerCase())); if(v) return v;}
    const rules={Female:/female|zira|samantha|aria|jenny|heera|google uk english female/i,
                 Male:/(^|\\W)male|david|daniel|guy|mark|ravi|google uk english male/i};
    if(cfg.pref==='British') return vs.find(v=>v.lang==='en-GB')||null;
    if(cfg.pref==='Indian English') return vs.find(v=>v.lang==='en-IN')||null;
    if(rules[cfg.pref]) return vs.find(v=>rules[cfg.pref].test(v.name)&&v.lang.startsWith('en'))||null;
    return null;
  };
  const go=()=>{
    speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(text);
    u.rate=cfg.rate;u.pitch=cfg.pitch;u.volume=cfg.volume;
    const v=pickVoice(); if(v){u.voice=v;u.lang=v.lang;}
    speechSynthesis.speak(u);
  };
  if(speechSynthesis.getVoices().length) go(); else speechSynthesis.onvoiceschanged=go;
  if(cfg.notify && 'Notification' in window && Notification.permission==='granted'){
    try{new Notification(%(title)s,{body:text.slice(0,140)});}catch(e){}
  }
})();
</script>
"""


def _speak_offline(text, s):
    """Server-side TTS through pyttsx3 (works when Jarvis runs on your own PC)."""
    try:
        import pyttsx3
    except ImportError:
        return False

    def run():
        try:
            eng = pyttsx3.init()
            eng.setProperty("rate", int(175 * float(s.get("tts_rate", 1.0))))
            eng.setProperty("volume", float(s.get("tts_volume", 1.0)))
            pref = s.get("tts_voice_pref", "Auto")
            if pref in ("Female", "Male"):
                for v in eng.getProperty("voices"):
                    hit = any(k in v.name.lower() for k in (("zira", "female", "samantha", "hazel") if pref == "Female"
                                                            else ("david", "male", "daniel", "mark")))
                    if hit:
                        eng.setProperty("voice", v.id)
                        break
            eng.say(text)
            eng.runAndWait()
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()
    return True


def speak_and_notify(text, title="Jarvis Notification", force=False):
    """Toast + spoken output using the voice settings from the sidebar."""
    st.toast((text or "")[:220], icon="🤖")
    s = st.session_state.get("settings", {})
    engine = s.get("tts_engine", "Browser (online)")
    if engine == "Off" or not (s.get("tts_enabled", True) or force):
        return
    spoken = clean_for_speech(text)
    if not spoken:
        return
    if engine.startswith("Offline") and _speak_offline(spoken, s):
        return
    cfg = {"rate": s.get("tts_rate", 1.0), "pitch": s.get("tts_pitch", 1.0), "volume": s.get("tts_volume", 1.0),
           "pref": s.get("tts_voice_pref", "Auto"), "name": s.get("tts_voice_name", ""), "notify": True}
    components.html(_VOICE_JS % {"text": json.dumps(spoken), "cfg": json.dumps(cfg), "title": json.dumps(title)}, height=0)


def transcribe_audio(client, audio_bytes, model="whisper-large-v3", language=None):
    """Groq Whisper. Sends bytes straight from memory - no temp files."""
    kwargs = {"model": model, "file": ("speech.wav", audio_bytes)}
    if language:
        kwargs["language"] = language
    return client.audio.transcriptions.create(**kwargs).text


def render_notification_permission_button():
    # Browsers only allow the permission prompt from a real click, so this is a real button.
    components.html("""
    <button id="b" style="padding:.45rem 1rem;border-radius:10px;border:1px solid #00e5ff55;background:#120a24;color:#e8f4ff;cursor:pointer;font:14px sans-serif">
      🔔 Enable desktop notifications</button>
    <script>
    const b=document.getElementById('b');
    if(!('Notification' in window)){b.textContent='Notifications not supported in this browser';b.disabled=true;}
    else if(Notification.permission==='granted'){b.textContent='🔔 Notifications enabled';}
    b.onclick=()=>Notification.requestPermission().then(p=>{b.textContent=p==='granted'?'🔔 Notifications enabled':'🔕 Notifications blocked';});
    </script>""", height=46)


def render_wake_word(enabled, phrase="hey jarvis", lang="en-IN"):
    """Hands-free trigger using the browser's SpeechRecognition (Chrome/Edge).

    Say '<wake phrase> <command>' and the command is submitted to the chat box.
    If you only say the phrase, the next sentence is used as the command.
    """
    if not enabled:
        return
    components.html("""
    <div id="s" style="font:13px sans-serif;color:#8a93b8;padding:2px 0">👂 starting wake word...</div>
    <script>
    (function(){
      const PHRASE=%(phrase)s.toLowerCase(), LANG=%(lang)s;
      const SR=window.SpeechRecognition||window.webkitSpeechRecognition, s=document.getElementById('s');
      if(!SR){s.textContent='Wake word needs Chrome or Edge.';return;}
      const doc=window.parent.document; let armed=false;
      function submit(text){
        const ta=doc.querySelector('[data-testid="stChatInputTextArea"]')||doc.querySelector('[data-testid="stChatInput"] textarea');
        if(!ta) return;
        const setter=Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype,'value').set;
        setter.call(ta,text); ta.dispatchEvent(new Event('input',{bubbles:true}));
        setTimeout(()=>{const b=doc.querySelector('[data-testid="stChatInputSubmitButton"]');
          if(b) b.click(); else ta.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));},180);
      }
      const r=new SR(); r.continuous=true; r.interimResults=false; r.lang=LANG;
      r.onresult=e=>{
        if(window.speechSynthesis&&speechSynthesis.speaking) return;   // don't hear Jarvis himself
        const t=e.results[e.results.length-1][0].transcript.trim(), low=t.toLowerCase();
        if(armed){armed=false;s.textContent='👂 listening for "'+PHRASE+'"';submit(t);return;}
        const i=low.indexOf(PHRASE);
        if(i<0) return;
        const cmd=t.slice(i+PHRASE.length).replace(/^[ ,.:;-]+/,'');
        if(cmd.length>2) submit(cmd); else {armed=true;s.textContent='🎙️ yes? say your command...';}
      };
      r.onend=()=>{try{r.start();}catch(e){}};
      r.onerror=ev=>{s.textContent='Wake word error: '+ev.error;};
      try{r.start();s.textContent='👂 listening for "'+PHRASE+'"';}catch(e){}
    })();
    </script>""" % {"phrase": json.dumps(phrase), "lang": json.dumps(lang)}, height=30)
