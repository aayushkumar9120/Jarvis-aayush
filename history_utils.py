"""Persistent, encrypted chat sessions (SQLite).

Replaces the single append-only chat_history_<user>.txt with named sessions the
user can reload from the sidebar. Old .txt files are imported automatically once.
"""
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime

from crypto_utils import decrypt_text, encrypt_text

DB_FILE = "jarvis_chats.db"


def _conn():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS sessions(
            id TEXT PRIMARY KEY, username TEXT NOT NULL, title TEXT NOT NULL,
            created TEXT NOT NULL, updated TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
            role TEXT NOT NULL, content TEXT NOT NULL, ts TEXT NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sess_user ON sessions(username, updated)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_msg_sess ON messages(session_id)")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def create_session(username, title="New chat"):
    init_db()
    sid = uuid.uuid4().hex[:12]
    with _conn() as c:
        c.execute("INSERT INTO sessions VALUES (?,?,?,?,?)",
                  (sid, username, encrypt_text(title), _now(), _now()))
    return sid


def list_sessions(username, limit=40):
    init_db()
    with _conn() as c:
        rows = c.execute("SELECT id,title,created,updated FROM sessions WHERE username=? "
                         "ORDER BY updated DESC LIMIT ?", (username, limit)).fetchall()
    return [{"id": r["id"], "title": decrypt_text(r["title"]), "created": r["created"],
             "updated": r["updated"]} for r in rows]


def _owns(c, session_id, username):
    return c.execute("SELECT 1 FROM sessions WHERE id=? AND username=?", (session_id, username)).fetchone()


def load_messages(session_id, username):
    init_db()
    with _conn() as c:
        if not _owns(c, session_id, username):
            return []
        rows = c.execute("SELECT role,content,ts FROM messages WHERE session_id=? ORDER BY id",
                         (session_id,)).fetchall()
    return [{"role": r["role"], "content": decrypt_text(r["content"]), "ts": r["ts"]} for r in rows]


def append_message(session_id, role, content):
    if not session_id:
        return
    with _conn() as c:
        c.execute("INSERT INTO messages(session_id,role,content,ts) VALUES (?,?,?,?)",
                  (session_id, role, encrypt_text(content), _now()))
        c.execute("UPDATE sessions SET updated=? WHERE id=?", (_now(), session_id))


def rename_session(session_id, username, title):
    with _conn() as c:
        if _owns(c, session_id, username):
            c.execute("UPDATE sessions SET title=? WHERE id=?", (encrypt_text(title.strip()[:60] or "Untitled"), session_id))


def delete_session(session_id, username):
    with _conn() as c:
        if _owns(c, session_id, username):
            c.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            c.execute("DELETE FROM sessions WHERE id=?", (session_id,))


def delete_all_sessions(username):
    for s in list_sessions(username, limit=10_000):
        delete_session(s["id"], username)


def make_title(text):
    t = re.sub(r"\s+", " ", re.sub(r"^/\w+\s*", "", text or "")).strip()
    return (t[:46] + "…") if len(t) > 47 else (t or "New chat")


def search_history(username, query, limit=3, exclude_session=None, scan=600):
    """Keyword recall across past sessions (content is encrypted, so we scan in Python)."""
    words = [w for w in re.findall(r"[a-zA-Z0-9]{4,}", (query or "").lower())][:8]
    if not words:
        return []
    init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT m.role,m.content,m.ts,m.session_id FROM messages m JOIN sessions s ON s.id=m.session_id "
            "WHERE s.username=? ORDER BY m.id DESC LIMIT ?", (username, scan)).fetchall()
    scored = []
    for r in rows:
        if r["session_id"] == exclude_session:
            continue
        text = decrypt_text(r["content"])
        low = text.lower()
        score = sum(1 for w in words if w in low)
        if score >= max(2, len(words) // 2) or (len(words) == 1 and score):
            scored.append((score, r["ts"], r["role"], text[:350]))
    scored.sort(key=lambda x: x[1], reverse=True)   # newest first...
    scored.sort(key=lambda x: -x[0])                # ...then best match first (stable)
    return [{"role": s[2], "ts": s[1], "text": s[3]} for s in scored[:limit]]


def stats():
    init_db()
    with _conn() as c:
        return {
            "sessions": c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
            "messages": c.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            "per_user": {r[0]: r[1] for r in c.execute(
                "SELECT username, COUNT(*) FROM sessions GROUP BY username")},
        }


# ---------------- export ----------------
def _clean(messages):
    return [{"role": m["role"], "content": m["content"], "ts": m.get("ts", "")} for m in messages]


def export_json(messages, title="Jarvis chat"):
    return json.dumps({"title": title, "exported": _now(), "messages": _clean(messages)},
                      indent=2, ensure_ascii=False).encode("utf-8")


def export_markdown(messages, title="Jarvis chat"):
    out = [f"# {title}", f"_Exported {_now()}_", ""]
    for m in messages:
        who = "🧑 You" if m["role"] == "user" else "🤖 Jarvis"
        out += [f"### {who}", m["content"], ""]
    return "\n".join(out).encode("utf-8")


def export_txt(messages):
    return "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages).encode("utf-8")


# ---------------- legacy import ----------------
def import_legacy_txt(username):
    """One-time import of chat_history_<user>.txt into a session. Returns session id or None."""
    safe = "".join(c for c in username if c.isalnum() or c in "_-")
    path = f"chat_history_{safe}.txt"
    flag = path + ".imported"
    if not os.path.exists(path) or os.path.exists(flag):
        return None
    msgs = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for block in f.read().split("---MESSAGE_SPLIT---"):
                if ":" in block:
                    role, content = block.strip().split(":", 1)
                    role = role.strip().lower()
                    if role in ("user", "assistant") and content.strip():
                        msgs.append((role, content.strip()))
        if not msgs:
            return None
        sid = create_session(username, "Imported history (.txt)")
        for role, content in msgs:
            append_message(sid, role, content)
        open(flag, "w").write("imported")
        return sid
    except Exception:
        return None
