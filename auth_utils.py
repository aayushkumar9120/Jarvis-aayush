"""Users, roles (RBAC), hashed passwords, lockout and audit log.

All original function names/signatures are preserved.
"""
import json
import os
import time
from datetime import datetime

from crypto_utils import hash_password, is_hashed, verify_password

USERS_FILE = "users.json"
MEMORY_FILE = "jarvis_memory.txt"
AUDIT_FILE = "audit_log.jsonl"

DEFAULT_ADMIN = "Aayush"
DEFAULT_ADMIN_PASSWORD = "123098"   # hashed on first run - change it in Admin > Passwords
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300

DEFAULT_MEMORY = """You are Jarvis, an advanced AI assistant created by Aayush. You maintain a Stark-inspired professional demeanor, highly capable in advanced mathematics, physics, and software engineering. You are assisting Aayush (Class 10) with his studies and technical projects."""

# ---------------- Role-Based Access Control ----------------
# chat: talk to Jarvis | web: search/fetch/news | vision: image & PDF Q&A
# image: image generation | pdf: PDF tools | tasks: reminders/tasks/timetable
# export: download history | email: send mail | system: clipboard & screen access
# admin: admin dashboard
ROLE_PERMISSIONS = {
    "admin": {"*"},
    "power user": {"chat", "web", "vision", "image", "pdf", "tasks", "export", "email", "system"},
    "normal user": {"chat", "web", "vision", "image", "pdf", "tasks", "export"},
    "guest": {"chat"},
}
ROLES = list(ROLE_PERMISSIONS.keys())


def normalize_role(role):
    role = (role or "normal user").strip().lower()
    return role if role in ROLE_PERMISSIONS else "normal user"


def has_permission(role, permission) -> bool:
    perms = ROLE_PERMISSIONS.get(normalize_role(role), set())
    return "*" in perms or permission in perms


# ---------------- users ----------------
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {
        DEFAULT_ADMIN: {
            "password": DEFAULT_ADMIN_PASSWORD, "role": "admin",
            "school": "Aayush Technology High", "title_pref": "Sir", "name": "Aayush",
            "class": "10", "email": "example@gmail.com",
        }
    }


def save_users(users_data):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4)
    except Exception:
        pass


def ensure_default_admin():
    """Create the default admin if missing and hash any legacy plain-text passwords."""
    users = load_users()
    changed = not os.path.exists(USERS_FILE)
    if DEFAULT_ADMIN not in users:
        users[DEFAULT_ADMIN] = {
            "password": DEFAULT_ADMIN_PASSWORD, "role": "admin",
            "school": "Aayush Technology High", "title_pref": "Sir", "name": "Aayush",
            "class": "10", "email": "example@gmail.com",
        }
        changed = True
    for data in users.values():
        if not is_hashed(data.get("password", "")):
            data["password"] = hash_password(str(data.get("password", "")))
            changed = True
        role = normalize_role(data.get("role"))
        if data.get("role") != role:
            data["role"] = role
            changed = True
    if changed:
        save_users(users)
    return users


def add_or_update_detailed_user(username, password, role, details):
    users = load_users()
    user = users.get(username, {})
    user.update({
        "password": password if is_hashed(password) else hash_password(password),
        "role": normalize_role(role),
        "school": details.get("school", user.get("school", "Aayush Technology High")),
        "title_pref": details.get("title_pref", user.get("title_pref", "Sir")),
        "name": details.get("name", user.get("name", username)),
        "class": details.get("class", user.get("class", "10")),
        "email": details.get("email", user.get("email", "")),
        "phone": details.get("phone", user.get("phone", "")),
    })
    users[username] = user
    save_users(users)


def _admin_count(users):
    return sum(1 for u in users.values() if normalize_role(u.get("role")) == "admin")


def delete_user(username):
    users = load_users()
    if username in users and username != DEFAULT_ADMIN:
        if normalize_role(users[username].get("role")) == "admin" and _admin_count(users) <= 1:
            return False
        del users[username]
        save_users(users)
        audit_log("user_deleted", detail=username)
        return True
    return False


def change_password(username, new_password):
    users = load_users()
    if username in users:
        users[username]["password"] = hash_password(new_password)
        users[username].pop("failed_attempts", None)
        users[username].pop("locked_until", None)
        save_users(users)
        audit_log("password_changed", user=username)


def update_user_role(username, role):
    users = load_users()
    if username not in users:
        return False
    role = normalize_role(role)
    if normalize_role(users[username].get("role")) == "admin" and role != "admin" and _admin_count(users) <= 1:
        return False  # never demote the last admin
    users[username]["role"] = role
    save_users(users)
    audit_log("role_changed", user=username, detail=role)
    return True


def uses_default_password(username) -> bool:
    u = load_users().get(username)
    return bool(u) and username == DEFAULT_ADMIN and verify_password(DEFAULT_ADMIN_PASSWORD, u.get("password", ""))


def verify_user(username, password):
    """Returns (ok, message). Applies lockout after repeated failures."""
    users = load_users()
    user = users.get(username)
    if not user:
        return False, "Invalid username or passcode."
    locked_until = user.get("locked_until", 0)
    if locked_until and time.time() < locked_until:
        mins = int((locked_until - time.time()) // 60) + 1
        return False, f"Account locked after too many failed attempts. Try again in ~{mins} min."
    if verify_password(password, user.get("password", "")):
        if user.get("failed_attempts") or user.get("locked_until"):
            user["failed_attempts"], user["locked_until"] = 0, 0
            save_users(users)
        audit_log("login_ok", user=username)
        return True, "OK"
    user["failed_attempts"] = user.get("failed_attempts", 0) + 1
    if user["failed_attempts"] >= MAX_FAILED_ATTEMPTS:
        user["locked_until"] = time.time() + LOCKOUT_SECONDS
        user["failed_attempts"] = 0
    save_users(users)
    audit_log("login_failed", user=username)
    return False, "Invalid Passcode! (Invalid username or password)"


# ---------------- audit log ----------------
def audit_log(event, user="", detail=""):
    try:
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"),
                                "event": event, "user": user, "detail": detail}) + "\n")
    except Exception:
        pass


def read_audit_log(limit=200):
    if not os.path.exists(AUDIT_FILE):
        return []
    try:
        with open(AUDIT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
        return [json.loads(l) for l in reversed(lines) if l.strip()]
    except Exception:
        return []


# ---------------- master memory ----------------
def get_jarvis_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return DEFAULT_MEMORY
    save_jarvis_memory(DEFAULT_MEMORY)
    return DEFAULT_MEMORY


def save_jarvis_memory(content):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass


def load_permanent_memory():
    return get_jarvis_memory()


def auto_save_memory(text):
    save_jarvis_memory(text)


def get_current_date():
    return datetime.now().strftime("%Y-%m-%d")
