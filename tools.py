"""Local tools for Buddy, the desktop pet AI.

Everything here runs on the user's own computer using only the Python
standard library. No data is sent anywhere. Functions raise ToolError with a
human-readable message when something cannot be done, so the chat brain can
report failures honestly instead of pretending.
"""
import ast
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime


class ToolError(Exception):
    pass


def get_data_dir():
    """Folder where Buddy keeps notes and settings (per-user, local only)."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, "DeskPetAI")
    else:
        path = os.path.join(os.path.expanduser("~"), ".deskpetai")
    os.makedirs(path, exist_ok=True)
    return path


# ------------------------------------------------------------------ calculator

def safe_calculate(expr):
    """Evaluate a simple arithmetic expression safely (no eval, no names)."""
    expr = expr.strip()
    if not expr or len(expr) > 200:
        raise ToolError("That calculation looks empty or too long.")
    allowed = set("0123456789.+-*/%() ")
    if any(ch not in allowed for ch in expr):
        raise ToolError("I can only calculate numbers with + - * / % and brackets.")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise ToolError("I couldn't understand that calculation.")
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp,
                                 ast.Constant, ast.Add, ast.Sub, ast.Mult,
                                 ast.Div, ast.Mod, ast.Pow, ast.FloorDiv,
                                 ast.USub, ast.UAdd)):
            raise ToolError("I can only calculate plain arithmetic.")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ToolError("I can only calculate plain numbers.")
    try:
        result = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, {})
    except ZeroDivisionError:
        raise ToolError("Can't divide by zero!")
    except Exception:
        raise ToolError("That calculation didn't work out.")
    return result


# ------------------------------------------------------------------ files

def resolve_path(path):
    stripped = path.strip().strip('"').strip("'")
    # "onedrive" means the user's synced OneDrive folder, if it exists.
    if stripped.lower() == "onedrive":
        return os.path.normpath(os.path.join(os.path.expanduser("~"), "OneDrive"))
    path = os.path.expanduser(stripped)
    if not os.path.isabs(path):
        path = os.path.join(os.path.expanduser("~"), path)
    return os.path.normpath(path)


def list_files(path):
    path = resolve_path(path or "~")
    if not os.path.isdir(path):
        raise ToolError(f"There is no folder at {path}.")
    entries = sorted(os.listdir(path))
    if not entries:
        return f"The folder {path} is empty.", []
    lines = []
    for name in entries[:100]:
        full = os.path.join(path, name)
        kind = "folder" if os.path.isdir(full) else "file"
        lines.append(f"{name} ({kind})")
    extra = f"\n...and {len(entries) - 100} more." if len(entries) > 100 else ""
    return f"Files in {path}:\n" + "\n".join(lines) + extra, entries


def read_file(path):
    path = resolve_path(path)
    if not os.path.isfile(path):
        raise ToolError(f"I can't find a file at {path}.")
    size = os.path.getsize(path)
    if size > 200_000:
        raise ToolError("That file is bigger than 200 KB, so I won't open it fully.")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        raise ToolError(f"I couldn't read that file: {e}.")


def create_file(path, content):
    path = resolve_path(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content or "")
    except OSError as e:
        raise ToolError(f"I couldn't write that file: {e}.")
    return path


def delete_file(path):
    path = resolve_path(path)
    if os.path.isdir(path):
        raise ToolError("I only delete single files, not whole folders, to stay safe.")
    if not os.path.isfile(path):
        raise ToolError(f"There is no file at {path} to delete.")
    try:
        os.remove(path)
    except OSError as e:
        raise ToolError(f"I couldn't delete that file: {e}.")
    return path


def _searchable_text(full):
    """Best-effort text for searching inside a file (any supported type)."""
    ext = os.path.splitext(full)[1].lower()
    try:
        if ext == ".docx":
            from docs import read_document_text
            return read_document_text(full)
        if ext == ".xlsx":
            from office import read_spreadsheet_text
            return read_spreadsheet_text(full)
        if ext == ".pdf":
            from office import read_pdf_text
            return read_pdf_text(full)
        if os.path.getsize(full) > 5_000_000:
            return ""
        with open(full, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except (OSError, ToolError, ValueError):
        return ""


def search_files(query, path):
    path = resolve_path(path or "~")
    if not os.path.isdir(path):
        raise ToolError(f"There is no folder at {path}.")
    query = query.lower()
    hits = []
    for root, dirs, files in os.walk(path):
        # Skip noisy / huge system folders on Windows and hidden caches.
        dirs[:] = [d for d in dirs
                   if d.lower() not in ("windows", "program files",
                                        "program files (x86)", "$recycle.bin")
                   and not d.startswith(".")]
        for name in files:
            full = os.path.join(root, name)
            if name.lower().endswith((".txt", ".md", ".py", ".json", ".csv",
                                       ".log", ".docx", ".xlsx", ".pdf")):
                if query in _searchable_text(full).lower():
                    hits.append(full)
            if len(hits) >= 50:
                break
        if len(hits) >= 50:
            break
    return hits


# ------------------------------------------------------------------ notes

def _notes_path():
    return os.path.join(get_data_dir(), "notes.json")


def load_notes():
    try:
        with open(_notes_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_note(text):
    notes = load_notes()
    notes.append({"text": text, "time": datetime.now().strftime("%Y-%m-%d %H:%M")})
    with open(_notes_path(), "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2)
    return len(notes)


# ------------------------------------------------------------------ settings

def _settings_path():
    return os.path.join(get_data_dir(), "settings.json")


def load_settings():
    try:
        with open(_settings_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    with open(_settings_path(), "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


# ------------------------------------------------------------------ apps / web

WINDOWS_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "files": "explorer.exe",
    "file explorer": "explorer.exe",
    "wordpad": "write.exe",
    "cmd": "cmd.exe",
    "terminal": "cmd.exe",
    "browser": None,  # handled with webbrowser
    "chrome": None,
    "edge": None,
    # Microsoft Office (desktop apps).
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    "onenote": "onenote",
    "access": "msaccess",
    # Other everyday apps (launched by name via Windows start).
    "vscode": "code",
    "code": "code",
    "spotify": "spotify",
    "whatsapp": "whatsapp",
    "zoom": "zoom",
    "vlc": "vlc",
    "firefox": "firefox",
}

# Office executables to look for in the standard install folders first,
# so "open word" works even when Office is not on the PATH.
OFFICE_EXES = {
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "outlook": "OUTLOOK.EXE",
    "onenote": "ONENOTE.EXE",
}


def _office_exe_path(exe):
    if os.name != "nt":
        return None
    for base in (os.environ.get("ProgramFiles", ""),
                 os.environ.get("ProgramFiles(x86)", "")):
        for sub in ("Microsoft Office\\root\\Office16",
                    "Microsoft Office\\Office16",
                    "Microsoft Office\\root\\Office15",
                    "Microsoft Office\\Office15"):
            candidate = os.path.join(base, sub, exe)
            if candidate and os.path.isfile(candidate):
                return candidate
    return None


def open_app(name, launcher=None):
    """Launch an app. `launcher` is injectable for tests."""
    name = name.strip()
    key = name.lower()
    if launcher is not None:
        launcher(name)
        return name
    if key in ("browser", "chrome", "edge"):
        webbrowser.open("https://www.google.com")
        return name
    if os.name == "nt":
        target = WINDOWS_APPS.get(key, name)
        office = (_office_exe_path(OFFICE_EXES[key])
                  if key in OFFICE_EXES else None)
        try:
            if office:
                os.startfile(office)  # noqa: S606 (user's own requested app)
            elif target.endswith(".exe") or os.path.isfile(target):
                os.startfile(target)  # noqa: S606 (user's own requested app)
            else:
                # Windows start resolves App Paths, so most installed apps
                # open by name even when they are not on the PATH.
                subprocess.Popen(["cmd", "/c", "start", "", target],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        except OSError as e:
            raise ToolError(f"I couldn't open {name}: {e}.")
        return name
    # Non-Windows fallback (used for testing here on Linux).
    try:
        subprocess.Popen(["xdg-open", name], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except OSError as e:
        raise ToolError(f"I couldn't open {name}: {e}.")
    return name


def open_app_with_file(app, path, launcher=None):
    """Open a file inside a chosen app (e.g. Word with Report.docx)."""
    app = app.strip()
    path = resolve_path(path)
    if not os.path.exists(path):
        raise ToolError(f"I can't find a file at {path}.")
    if launcher is not None:
        launcher(app, path)
        return app
    if os.name == "nt":
        key = app.lower()
        target = WINDOWS_APPS.get(key, app)
        office = _office_exe_path(OFFICE_EXES[key]) if key in OFFICE_EXES else None
        try:
            if office:
                subprocess.Popen([office, path],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            elif target.endswith(".exe") or os.path.isfile(target):
                subprocess.Popen([target, path],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(["cmd", "/c", "start", "", target, path],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        except OSError as e:
            raise ToolError(f"I couldn't open {app} with that file: {e}.")
        return app
    return open_file(path)


def web_search(query, opener=None):
    url = "https://duckduckgo.com/?q=" + query.replace(" ", "+")
    if opener is not None:
        opener(url)
    else:
        webbrowser.open(url)
    return url


# ------------------------------------------------------------------ system

def system_info():
    info = {
        "System": platform.system(),
        "Release": platform.release(),
        "Version": platform.version(),
        "Machine": platform.machine(),
        "Processor": platform.processor() or "unknown",
        "CPU cores": os.cpu_count(),
        "Python": sys.version.split()[0],
    }
    try:
        disk = shutil.disk_usage(os.path.expanduser("~"))
        info["Disk free (GB)"] = round(disk.free / (1024 ** 3), 1)
        info["Disk total (GB)"] = round(disk.total / (1024 ** 3), 1)
    except OSError:
        pass
    return info


# ------------------------------------------------------------------ reminders

class ReminderService:
    """Simple in-process reminders; the UI supplies the popup callback."""

    def __init__(self):
        self.timers = []

    def remind_in(self, seconds, message, callback):
        timer = threading.Timer(seconds, callback, args=[message])
        timer.daemon = True
        timer.start()
        self.timers.append(timer)
        return timer

    def remind_every(self, seconds, message, callback):
        """Recurring reminder while the app runs (e.g. every 30 minutes)."""
        def _fire():
            callback(message)
            self.remind_every(seconds, message, callback)
        timer = threading.Timer(seconds, _fire)
        timer.daemon = True
        timer.start()
        self.timers.append(timer)
        return timer


# ------------------------------------------------------------------ more files

def copy_file(src, dest):
    src, dest = resolve_path(src), resolve_path(dest)
    if not os.path.isfile(src):
        raise ToolError(f"I can't find a file at {src}.")
    if os.path.isdir(dest):
        dest = os.path.join(dest, os.path.basename(src))
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        shutil.copy2(src, dest)
    except OSError as e:
        raise ToolError(f"I couldn't copy that file: {e}.")
    return dest


def move_file(src, dest):
    dest = copy_file(src, dest)
    try:
        os.remove(resolve_path(src))
    except OSError:
        pass
    return dest


def rename_file(src, new_name):
    src = resolve_path(src)
    if not os.path.exists(src):
        raise ToolError(f"I can't find anything at {src}.")
    dest = os.path.join(os.path.dirname(src), new_name.strip())
    try:
        os.rename(src, dest)
    except OSError as e:
        raise ToolError(f"I couldn't rename it: {e}.")
    return dest


def create_folder(path):
    path = resolve_path(path)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        raise ToolError(f"I couldn't create that folder: {e}.")
    return path


def file_info(path):
    path = resolve_path(path)
    if not os.path.exists(path):
        raise ToolError(f"Nothing exists at {path}.")
    st = os.stat(path)
    kind = "folder" if os.path.isdir(path) else "file"
    modified = datetime.fromtimestamp(st.st_mtime).strftime("%d %B %Y, %I:%M %p")
    return {"path": path, "kind": kind, "size_bytes": st.st_size,
            "modified": modified}


def recent_files(path, count=10):
    path = resolve_path(path or "~")
    if not os.path.isdir(path):
        raise ToolError(f"There is no folder at {path}.")
    files = []
    for name in os.listdir(path):
        full = os.path.join(path, name)
        if os.path.isfile(full):
            files.append((os.path.getmtime(full), name))
    files.sort(reverse=True)
    return [name for _, name in files[:count]]


def read_any(path):
    """Read a file as text, whatever its type (txt/md/csv/json/docx)."""
    path = resolve_path(path)
    if not os.path.isfile(path):
        raise ToolError(f"I can't find a file at {path}.")
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        from docs import read_document_text
        return read_document_text(path)
    if os.path.getsize(path) > 200_000:
        raise ToolError("That file is bigger than 200 KB, so I won't open it fully.")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        raise ToolError(f"I couldn't read that file: {e}.")


def file_stats(path):
    text = read_any(path)
    words = len(text.split())
    lines = text.count("\n") + (1 if text else 0)
    return {"words": words, "lines": lines, "chars": len(text), "text": text}


def write_csv(path, headers, rows):
    import csv
    path = resolve_path(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if headers:
                writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
    except OSError as e:
        raise ToolError(f"I couldn't write that spreadsheet: {e}.")
    return path


def open_file(path, launcher=None):
    path = resolve_path(path)
    if not os.path.exists(path):
        raise ToolError(f"Nothing exists at {path}.")
    if launcher is not None:
        launcher(path)
        return path
    if os.name == "nt":
        try:
            os.startfile(path)  # noqa: S606 (user's own requested file)
        except OSError as e:
            raise ToolError(f"I couldn't open that file: {e}.")
    else:
        try:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError as e:
            raise ToolError(f"I couldn't open that file: {e}.")
    return path


# ------------------------------------------------------------------ bulk + cleanup

def find_rename_matches(folder, old, new):
    folder = resolve_path(folder)
    if not os.path.isdir(folder):
        raise ToolError(f"There is no folder at {folder}.")
    matches = []
    for name in sorted(os.listdir(folder)):
        if old in name and os.path.isfile(os.path.join(folder, name)):
            matches.append((name, name.replace(old, new)))
    return matches


def do_bulk_rename(folder, matches):
    folder = resolve_path(folder)
    done, failed = [], []
    for old_name, new_name in matches:
        try:
            os.rename(os.path.join(folder, old_name),
                      os.path.join(folder, new_name))
            done.append((old_name, new_name))
        except OSError as e:
            failed.append((old_name, str(e)))
    return done, failed


def find_large_files(path, count=10):
    path = resolve_path(path or "~")
    if not os.path.isdir(path):
        raise ToolError(f"There is no folder at {path}.")
    found = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            full = os.path.join(root, name)
            try:
                found.append((os.path.getsize(full), full))
            except OSError:
                pass
    found.sort(reverse=True)
    return found[:count]


def find_duplicates(path):
    import hashlib
    path = resolve_path(path or "~")
    if not os.path.isdir(path):
        raise ToolError(f"There is no folder at {path}.")
    by_size = {}
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            full = os.path.join(root, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size > 100_000_000:
                continue
            by_size.setdefault(size, []).append(full)
    groups = []
    for size, candidates in by_size.items():
        if len(candidates) < 2 or size == 0:
            continue
        by_hash = {}
        for full in candidates:
            try:
                h = hashlib.md5()
                with open(full, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                by_hash.setdefault(h.hexdigest(), []).append(full)
            except OSError:
                pass
        for same in by_hash.values():
            if len(same) > 1:
                groups.append(same)
    return groups


def find_temp_files(path):
    path = resolve_path(path or "~")
    if not os.path.isdir(path):
        raise ToolError(f"There is no folder at {path}.")
    hits = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            low = name.lower()
            if low.endswith((".tmp", ".log", ".bak")) or low.startswith("~"):
                hits.append(os.path.join(root, name))
            if len(hits) >= 100:
                return hits
    return hits


# ------------------------------------------------------------------ data

def clean_csv(src, dest=None):
    import csv
    src = resolve_path(src)
    if dest is None:
        base, ext = os.path.splitext(src)
        dest = base + "_cleaned" + (ext or ".csv")
    else:
        dest = resolve_path(dest)
    try:
        with open(src, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
    except OSError as e:
        raise ToolError(f"I couldn't read that file: {e}.")
    seen, cleaned = set(), []
    for row in rows:
        row = [c.strip() for c in row]
        if not any(row):
            continue
        key = tuple(row)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(row)
    try:
        with open(dest, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(cleaned)
    except OSError as e:
        raise ToolError(f"I couldn't write that file: {e}.")
    return dest, len(rows), len(cleaned)


def pivot_csv(path, group_col, sum_col=None):
    import csv
    path = resolve_path(path)
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or group_col not in reader.fieldnames:
                raise ToolError(f"Column '{group_col}' not found in that file.")
            if sum_col and sum_col not in reader.fieldnames:
                raise ToolError(f"Column '{sum_col}' not found in that file.")
            groups = {}
            for row in reader:
                key = (row.get(group_col) or "").strip()
                entry = groups.setdefault(key, {"count": 0, "sum": 0.0})
                entry["count"] += 1
                if sum_col:
                    try:
                        entry["sum"] += float(row.get(sum_col) or 0)
                    except ValueError:
                        pass
    except OSError as e:
        raise ToolError(f"I couldn't read that file: {e}.")
    return groups


# ------------------------------------------------------------------ code / git / db / http

def run_python(path, timeout=15):
    path = resolve_path(path)
    if not os.path.isfile(path):
        raise ToolError(f"I can't find a file at {path}.")
    try:
        proc = subprocess.run([sys.executable, path], capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ToolError(f"That script ran longer than {timeout} seconds, so I stopped it.")
    except OSError as e:
        raise ToolError(f"I couldn't run that file: {e}.")
    out = (proc.stdout or "")[-2000:]
    err = (proc.stderr or "")[-1000:]
    return proc.returncode, out, err


def check_python(path):
    import py_compile
    path = resolve_path(path)
    if not os.path.isfile(path):
        raise ToolError(f"I can't find a file at {path}.")
    try:
        py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as e:
        raise ToolError(f"Syntax problem: {e}.")
    return True


def git_info(path, kind):
    path = resolve_path(path or ".")
    if shutil.which("git") is None:
        raise ToolError("Git isn't installed on this computer.")
    args = ["git", "-C", path, "status", "--short"] if kind == "status" \
        else ["git", "-C", path, "log", "--oneline", "-10"]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except OSError as e:
        raise ToolError(f"Git failed: {e}.")
    if proc.returncode != 0:
        raise ToolError("That folder doesn't look like a Git repository.")
    return proc.stdout.strip() or "(nothing to show)"


def sqlite_select(db_path, sql):
    import sqlite3
    db_path = resolve_path(db_path)
    if not os.path.isfile(db_path):
        raise ToolError(f"I can't find a database at {db_path}.")
    cleaned = sql.strip().rstrip(";")
    first = cleaned.split(None, 1)[0].upper() if cleaned.split() else ""
    if first not in ("SELECT", "WITH", "PRAGMA"):
        raise ToolError("For safety I only run SELECT queries on databases.")
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.execute(cleaned)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(100)
        conn.close()
    except Exception as e:
        raise ToolError(f"That query failed: {e}.")
    return columns, rows


def http_get(url):
    import urllib.error
    import urllib.request
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    req = urllib.request.Request(url, headers={"User-Agent": "DeskPetAI/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read(2000).decode("utf-8", errors="replace")
            return resp.status, text
    except urllib.error.HTTPError as e:
        raise ToolError(f"The site answered with an error: {e.code}.")
    except Exception as e:
        raise ToolError(f"I couldn't reach that site: {e}.")


# ------------------------------------------------------------------ memory / redact

def _facts_path():
    return os.path.join(get_data_dir(), "facts.json")


def load_facts():
    try:
        with open(_facts_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_fact(text):
    facts = load_facts()
    facts.append({"text": text, "time": datetime.now().strftime("%Y-%m-%d %H:%M")})
    with open(_facts_path(), "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2)
    return len(facts)


def redact_file(src, words, dest=None):
    import re as _re
    src = resolve_path(src)
    try:
        with open(src, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        raise ToolError(f"I couldn't read that file: {e}.")
    if dest is None:
        base, ext = os.path.splitext(src)
        dest = base + "_redacted" + (ext or ".txt")
    else:
        dest = resolve_path(dest)
    total = 0
    for word in words:
        word = word.strip()
        if not word:
            continue
        text, n = _re.subn(_re.escape(word), "[REDACTED]", text,
                           flags=_re.IGNORECASE)
        total += n
    try:
        with open(dest, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError as e:
        raise ToolError(f"I couldn't write that file: {e}.")
    return dest, total


# ------------------------------------------------------------------ clipboard

_CLIPBOARD = {"text": None, "history": []}


def clipboard_copy(text, backend=None):
    if backend is not None:
        backend["set"](text)
    elif os.name == "nt":
        try:
            subprocess.run(["powershell", "-command", "Set-Clipboard",
                            "-Value", text], check=True, capture_output=True,
                           timeout=15)
        except Exception:
            _CLIPBOARD["text"] = text
    else:
        _CLIPBOARD["text"] = text
    _CLIPBOARD["history"].append(text)
    _CLIPBOARD["history"] = _CLIPBOARD["history"][-20:]
    return text


def clipboard_paste(backend=None):
    if backend is not None:
        return backend["get"]()
    if os.name == "nt":
        try:
            proc = subprocess.run(["powershell", "-command", "Get-Clipboard"],
                                  capture_output=True, text=True, timeout=15)
            if proc.stdout.strip():
                return proc.stdout.strip()
        except Exception:
            pass
    return _CLIPBOARD["text"]


def clipboard_history():
    return list(_CLIPBOARD["history"])


# ------------------------------------------------------------------ screenshot

def take_screenshot(path=None, grabber=None):
    if path is None:
        folder = os.path.join(os.path.expanduser("~"), "Pictures", "DeskPetAI")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "screenshot_" +
                            datetime.now().strftime("%Y%m%d_%H%M%S") + ".png")
    else:
        path = resolve_path(path)
    if grabber is not None:
        grabber(path)
        return path
    try:
        from PIL import ImageGrab
    except ImportError:
        raise ToolError("Screenshots need Pillow, which isn't installed. "
                        "Install it once with: pip install pillow — then "
                        "ask me again.")
    try:
        ImageGrab.grab().save(path)
    except Exception as e:
        raise ToolError(f"I couldn't take a screenshot: {e}.")
    return path


# ------------------------------------------------------------------ startup

def _startup_link_path():
    return os.path.join(os.environ.get("APPDATA", ""),
                         "Microsoft", "Windows", "Start Menu", "Programs",
                         "Startup", "Buddy.lnk")


def startup_add():
    """Make Buddy start automatically when Windows starts (a Start Menu
    Startup shortcut pointing at start.bat). Windows only."""
    if os.name != "nt":
        raise ToolError("Starting with Windows only works on Windows.")
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0])) \
        if sys.argv and sys.argv[0] else os.getcwd()
    target = os.path.join(app_dir, "start.bat")
    link = _startup_link_path()

    def q(s):
        return "'" + s.replace("'", "''") + "'"

    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({q(link)}); "
          f"$s.TargetPath={q(target)}; $s.WorkingDirectory={q(app_dir)}; $s.Save()")
    try:
        subprocess.run(["powershell", "-command", ps], check=True,
                       capture_output=True, timeout=30)
    except Exception as e:
        raise ToolError(f"I couldn't add Buddy to startup: {e}.")
    return link


def startup_remove():
    """Stop Buddy starting automatically with Windows. Returns True if a
    startup shortcut was actually removed."""
    if os.name != "nt":
        raise ToolError("Starting with Windows only works on Windows.")
    link = _startup_link_path()
    if os.path.exists(link):
        try:
            os.remove(link)
        except OSError as e:
            raise ToolError(f"I couldn't remove it: {e}.")
        return True
    return False


# ------------------------------------------------------------------ voice

_speak_queue = None
_speak_worker = None


_SPEAK_VOLUME = 100


def set_voice_volume(volume):
    global _SPEAK_VOLUME
    _SPEAK_VOLUME = max(0, min(100, int(volume)))


def _speak_worker_loop():
    import queue as _queue
    while True:
        text = _speak_queue.get()
        if text is None:
            return
        ps_text = text.replace("'", "''")
        ps = (f"Add-Type -AssemblyName System.Speech; "
              f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"$s.Volume = {_SPEAK_VOLUME}; "
              f"$s.Speak('{ps_text}')")
        try:
            subprocess.run(["powershell", "-command", ps],
                           capture_output=True, timeout=60)
        except Exception:
            pass  # speaking is best-effort; never break the chat


def speak(text, runner=None):
    """Speak text aloud (Windows built-in voice, no installs, no cloud).

    With `runner` (tests), the runner is called with the text instead.
    Otherwise the text is queued for a background speaker thread so the
    chat never freezes while Buddy talks.
    """
    import queue as _queue
    import threading
    global _speak_queue, _speak_worker
    text = " ".join((text or "").split())[:500]
    if not text:
        return
    if runner is not None:
        runner(text)
        return
    if os.name != "nt":
        raise ToolError("Speaking aloud only works on Windows.")
    if _speak_queue is None:
        _speak_queue = _queue.Queue()
        _speak_worker = threading.Thread(target=_speak_worker_loop,
                                         daemon=True)
        _speak_worker.start()
    _speak_queue.put(text)


_LISTEN_PS = """
Add-Type -AssemblyName System.Speech
$rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine
$rec.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$rec.SetInputToDefaultAudioDevice()
$r = $rec.Recognize([TimeSpan]::FromSeconds(10))
if ($r) { $r.Text } else { "" }
"""


def listen(timeout=30, runner=None):
    """Listen to the microphone once and return the recognised text.

    Uses Windows' built-in speech recognition (offline, no installs).
    With `runner` (tests), the runner's return value is used instead.
    Returns "" when nothing was understood.
    """
    if runner is not None:
        return runner()
    if os.name != "nt":
        raise ToolError("Listening only works on Windows, with a microphone.")
    try:
        proc = subprocess.run(["powershell", "-command", _LISTEN_PS],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ""
    except OSError as e:
        raise ToolError(f"I couldn't use the microphone: {e}.")
    if proc.returncode != 0:
        raise ToolError("Windows speech recognition didn't start — check "
                        "your microphone and that speech recognition is "
                        "set up on this PC.")
    return (proc.stdout or "").strip()


# ------------------------------------------------------------------ sounds

def celebrate_sound():
    """A tiny happy chime when a task finishes (Windows beeps, no files).

    Best-effort and silent everywhere else: never raises, never blocks.
    """
    if os.name != "nt":
        return
    import threading

    def _play():
        try:
            import winsound
            for freq in (660, 880, 1320):
                winsound.Beep(freq, 120)
        except Exception:
            pass

    threading.Thread(target=_play, daemon=True).start()


# ------------------------------------------------------------------ work log

def _worklog_path():
    return os.path.join(get_data_dir(), "worklog.json")


def log_work(action, detail):
    try:
        entries = []
        try:
            with open(_worklog_path(), "r", encoding="utf-8") as f:
                entries = json.load(f)
        except (OSError, ValueError):
            entries = []
        entries.append({"action": action, "detail": detail,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M")})
        with open(_worklog_path(), "w", encoding="utf-8") as f:
            json.dump(entries[-100:], f, indent=2)
    except Exception:
        pass


def load_work_log():
    try:
        with open(_worklog_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


# ------------------------------------------------------------------ web tools

_DOWNLOAD_CATEGORIES = {
    "Images": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"},
    "Documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                  ".txt", ".md", ".csv"},
    "Audio": {".mp3", ".wav", ".ogg", ".flac", ".m4a"},
    "Video": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
}


def download_file(url, folder, opener=None):
    """Download a URL into folder/<Category>/filename (organised)."""
    import urllib.request
    folder = resolve_path(folder or "~/Downloads")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    name = os.path.basename(url.split("?")[0].split("#")[0]) or "download"
    name = "".join(c for c in name if c.isalnum() or c in "._-") or "download"
    ext = os.path.splitext(name)[1].lower()
    category = "Other"
    for cat, exts in _DOWNLOAD_CATEGORIES.items():
        if ext in exts:
            category = cat
            break
    dest_dir = os.path.join(folder, category)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, name)
    try:
        if opener is not None:
            data = opener(url)
            with open(dest, "wb") as f:
                f.write(data)
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "DeskPetAI/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp, \
                    open(dest, "wb") as f:
                shutil.copyfileobj(resp, f, length=65536)
    except Exception as e:
        raise ToolError(f"I couldn't download that: {e}.")
    return dest


def scrape_text(url, fetcher=None):
    """Fetch a page and return its readable text (scripts/tags stripped)."""
    import re as _re
    if fetcher is not None:
        html = fetcher(url)
    else:
        import urllib.request
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DeskPetAI/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read(500_000).decode("utf-8", errors="replace")
        except Exception as e:
            raise ToolError(f"I couldn't fetch that page: {e}.")
    html = _re.sub(r"<(script|style).*?</\1>", " ", html,
                   flags=_re.DOTALL | _re.IGNORECASE)
    text = _re.sub(r"<[^>]+>", " ", html)
    text = _re.sub(r"\s+", " ", text).strip()
    if not text:
        raise ToolError("That page had no readable text I could extract.")
    return text[:4000]


def research_topic(topic, fetcher=None):
    """Extractive web research: top results (title + link + snippet).

    Default source is DuckDuckGo Lite (no key needed). `fetcher` is
    injectable for tests: fetcher(topic) -> html string.
    """
    import re as _re
    import urllib.parse
    import urllib.request
    if fetcher is not None:
        html = fetcher(topic)
    else:
        query = urllib.parse.quote_plus(topic)
        try:
            req = urllib.request.Request(
                f"https://lite.duckduckgo.com/lite/?q={query}",
                headers={"User-Agent": "DeskPetAI/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read(500_000).decode("utf-8", errors="replace")
        except Exception as e:
            raise ToolError(f"I couldn't research that right now: {e}.")
    results = []
    for m in _re.finditer(
            r"class=['\"]result-link['\"][^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",
            html, flags=_re.DOTALL | _re.IGNORECASE):
        title = _re.sub(r"<[^>]+>", "", m.group(2)).strip()
        results.append({"title": title or "(no title)", "url": m.group(1),
                        "snippet": ""})
        if len(results) >= 8:
            break
    if not results:
        raise ToolError("No results came back for that topic. Try other words.")
    return results


# ------------------------------------------------------------------ git extras

def git_commit(folder, message):
    folder = resolve_path(folder or ".")
    if shutil.which("git") is None:
        raise ToolError("Git isn't installed on this computer.")
    for args in (["git", "-C", folder, "add", "-A"],
                 ["git", "-C", folder, "commit", "-m", message]):
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
        except OSError as e:
            raise ToolError(f"Git failed: {e}.")
        if proc.returncode != 0:
            out = (proc.stdout + proc.stderr).strip()
            if "nothing to commit" in out:
                raise ToolError("Nothing to commit — the folder is clean.")
            raise ToolError("That folder doesn't look like a Git repository.")
    return (proc.stdout or "").strip() or "Committed."


def git_branch(folder, name):
    folder = resolve_path(folder or ".")
    if shutil.which("git") is None:
        raise ToolError("Git isn't installed on this computer.")
    try:
        proc = subprocess.run(["git", "-C", folder, "checkout", "-b", name],
                              capture_output=True, text=True, timeout=30)
    except OSError as e:
        raise ToolError(f"Git failed: {e}.")
    if proc.returncode != 0:
        raise ToolError("Couldn't create that branch — are you in a Git repo, "
                        "and does the branch already exist?")
    return f"Created and switched to branch '{name}'."


# ------------------------------------------------------------------ scripts

def run_script(path, timeout=30):
    """Run a script by extension: .py anywhere; .ps1/.bat on Windows."""
    path = resolve_path(path)
    if not os.path.isfile(path):
        raise ToolError(f"I can't find a file at {path}.")
    ext = os.path.splitext(path)[1].lower()
    if ext == ".py":
        return run_python(path, timeout=timeout)
    if os.name != "nt":
        raise ToolError(f"{ext} scripts only run on Windows.")
    if ext == ".ps1":
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", path]
    elif ext in (".bat", ".cmd"):
        cmd = ["cmd", "/c", path]
    else:
        raise ToolError(f"I don't know how to run {ext} files.")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ToolError(f"That script ran longer than {timeout} seconds, so I stopped it.")
    except OSError as e:
        raise ToolError(f"I couldn't run that file: {e}.")
    return proc.returncode, (proc.stdout or "")[-2000:], (proc.stderr or "")[-1000:]


# ------------------------------------------------------------------ OS control

def wifi_toggle(on):
    if os.name != "nt":
        raise ToolError("Wi-Fi control only works on Windows.")
    state = "enable" if on else "disable"
    try:
        proc = subprocess.run(["netsh", "interface", "set", "interface",
                               "Wi-Fi", f"admin={state}"],
                              capture_output=True, text=True, timeout=30)
    except OSError as e:
        raise ToolError(f"I couldn't change Wi-Fi: {e}.")
    if proc.returncode != 0:
        raise ToolError("Wi-Fi couldn't be changed — the adapter may be named "
                        "differently, or Buddy needs administrator rights.")
    return f"Wi-Fi turned {'on' if on else 'off'}."


def set_brightness(level):
    if os.name != "nt":
        raise ToolError("Brightness control only works on Windows.")
    level = max(0, min(100, int(level)))
    ps = (f"(Get-WmiObject -Namespace root/WMI "
          f"-Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})")
    try:
        proc = subprocess.run(["powershell", "-command", ps],
                              capture_output=True, text=True, timeout=30)
    except OSError as e:
        raise ToolError(f"I couldn't change brightness: {e}.")
    if proc.returncode != 0:
        raise ToolError("Brightness couldn't be changed on this display.")
    return f"Brightness set to {level}%."


def power_action(action):
    if os.name != "nt":
        raise ToolError("Power actions only work on Windows.")
    cmds = {"sleep": ["rundll32", "powrprof.dll,SetSuspendState", "0", "1", "0"],
            "shutdown": ["shutdown", "/s", "/t", "5"],
            "restart": ["shutdown", "/r", "/t", "5"]}
    if action not in cmds:
        raise ToolError(f"Unknown power action: {action}.")
    try:
        subprocess.Popen(cmds[action], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except OSError as e:
        raise ToolError(f"I couldn't do that: {e}.")
    return f"{action.capitalize()} requested."


# ------------------------------------------------------------------ mail + calendar files

def read_email_file(path):
    """Read a saved .eml email file (subject, from, date, plain body)."""
    import email as _email
    from email import policy
    path = resolve_path(path)
    if not os.path.isfile(path):
        raise ToolError(f"I can't find a file at {path}.")
    try:
        with open(path, "rb") as f:
            msg = _email.message_from_binary_file(f, policy=policy.default)
    except Exception as e:
        raise ToolError(f"I couldn't read that email file: {e}.")
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body = part.get_content()
                except Exception:
                    pass
                break
    else:
        try:
            body = msg.get_content()
        except Exception:
            body = ""
    return {"from": msg.get("From", ""), "to": msg.get("To", ""),
            "subject": msg.get("Subject", ""), "date": msg.get("Date", ""),
            "body": (body or "")[:2000]}


def read_calendar_file(path):
    """Read a saved .ics calendar file -> list of events (sorted)."""
    import re as _re
    path = resolve_path(path)
    if not os.path.isfile(path):
        raise ToolError(f"I can't find a file at {path}.")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except OSError as e:
        raise ToolError(f"I couldn't read that file: {e}.")
    raw = _re.sub(r"\r?\n[ \t]", "", raw)  # unfold continuation lines
    events = []
    for block in _re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", raw, _re.DOTALL):
        def field(name):
            m = _re.search(rf"^{name}(?:;[^:]*)?:(.*)$", block, _re.MULTILINE)
            return m.group(1).strip() if m else ""
        events.append({"start": field("DTSTART"), "summary": field("SUMMARY"),
                       "location": field("LOCATION"),
                       "description": field("DESCRIPTION")})
    events.sort(key=lambda e: e["start"])
    return events


# ------------------------------------------------------------------ optional tools

def pdf_merge(paths, dest):
    """Merge PDFs (needs pypdf: pip install pypdf)."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        raise ToolError("Merging PDFs needs pypdf, which isn't installed. "
                        "Install it once with: pip install pypdf")
    writer = PdfWriter()
    for path in paths:
        full = resolve_path(path)
        if not os.path.isfile(full):
            raise ToolError(f"I can't find a file at {full}.")
        for page in PdfReader(full).pages:
            writer.add_page(page)
    dest = resolve_path(dest)
    try:
        with open(dest, "wb") as f:
            writer.write(f)
    except OSError as e:
        raise ToolError(f"I couldn't write that file: {e}.")
    return dest


def pdf_split(path, pages, dest):
    """Extract pages (1-based, e.g. '1,3' or '2-4') into one PDF (pypdf)."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        raise ToolError("Splitting PDFs needs pypdf, which isn't installed. "
                        "Install it once with: pip install pypdf")
    full = resolve_path(path)
    if not os.path.isfile(full):
        raise ToolError(f"I can't find a file at {full}.")
    wanted = set()
    for chunk in pages.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            wanted.update(range(int(a), int(b) + 1))
        elif chunk:
            wanted.add(int(chunk))
    reader = PdfReader(full)
    writer = PdfWriter()
    for num in sorted(wanted):
        if 1 <= num <= len(reader.pages):
            writer.add_page(reader.pages[num - 1])
    dest = resolve_path(dest)
    with open(dest, "wb") as f:
        writer.write(f)
    return dest


def image_to_pdf(src, dest):
    """Convert an image to PDF (needs Pillow: pip install pillow)."""
    try:
        from PIL import Image
    except ImportError:
        raise ToolError("Image conversion needs Pillow, which isn't installed. "
                        "Install it once with: pip install pillow")
    src, dest = resolve_path(src), resolve_path(dest)
    if not os.path.isfile(src):
        raise ToolError(f"I can't find a file at {src}.")
    try:
        Image.open(src).convert("RGB").save(dest, "PDF")
    except Exception as e:
        raise ToolError(f"I couldn't convert that image: {e}.")
    return dest


def ocr_image(path):
    """Extract text from an image (needs Pillow + pytesseract + Tesseract)."""
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        raise ToolError("OCR needs Pillow and pytesseract, plus the Tesseract "
                        "program. Install with: pip install pillow pytesseract "
                        "and download Tesseract for Windows.")
    path = resolve_path(path)
    if not os.path.isfile(path):
        raise ToolError(f"I can't find a file at {path}.")
    try:
        text = pytesseract.image_to_string(Image.open(path)).strip()
    except Exception as e:
        raise ToolError(f"OCR failed: {e}.")
    if not text:
        raise ToolError("No text could be read from that image.")
    return text


def media_convert(src, dest):
    """Convert audio/video with FFmpeg (needs the ffmpeg program)."""
    if shutil.which("ffmpeg") is None:
        raise ToolError("Media conversion needs FFmpeg, which isn't installed. "
                        "Download it from https://ffmpeg.org and add it to PATH.")
    src, dest = resolve_path(src), resolve_path(dest)
    if not os.path.isfile(src):
        raise ToolError(f"I can't find a file at {src}.")
    try:
        proc = subprocess.run(["ffmpeg", "-y", "-i", src, dest],
                              capture_output=True, text=True, timeout=300)
    except OSError as e:
        raise ToolError(f"I couldn't convert that: {e}.")
    if proc.returncode != 0:
        raise ToolError("FFmpeg couldn't convert that file.")
    return dest
