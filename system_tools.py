"""Clipboard & screen access. These read the machine Jarvis RUNS on, so they only make
sense when you run Jarvis locally - and they are gated behind the 'system' permission."""
import io
import os
import glob
import time


def read_clipboard():
    """-> (ok, text_or_error)"""
    try:
        import pyperclip
        text = pyperclip.paste()
    except Exception:
        try:
            import tkinter
            r = tkinter.Tk(); r.withdraw()
            text = r.clipboard_get(); r.destroy()
        except Exception as e:
            return False, f"Clipboard unavailable ({e}). Try: pip install pyperclip"
    text = (text or "").strip()
    return (True, text[:8000]) if text else (False, "The clipboard is empty.")


def write_clipboard(text):
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        return False


def take_screenshot():
    """-> (ok, png_bytes_or_error). Needs Pillow (Windows/macOS; Linux needs an X display)."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.thumbnail((1600, 1600))          # keep the vision payload small
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return True, buf.getvalue()
    except Exception as e:
        return False, f"Screenshot failed ({e}). Try: pip install pillow"


def latest_saved_screenshot(max_age_min=30):
    """Newest screenshot file from common folders -> (ok, (name, bytes)|error)."""
    home = os.path.expanduser("~")
    folders = [os.path.join(home, p) for p in ("Pictures/Screenshots", "Pictures", "Desktop", "OneDrive/Pictures/Screenshots")]
    files = []
    for d in folders:
        for ext in ("png", "jpg", "jpeg"):
            files += glob.glob(os.path.join(d, f"*.{ext}"))
    files = [f for f in files if time.time() - os.path.getmtime(f) <= max_age_min * 60]
    if not files:
        return False, f"No screenshot saved in the last {max_age_min} minutes."
    newest = max(files, key=os.path.getmtime)
    with open(newest, "rb") as f:
        return True, (os.path.basename(newest), f.read())
