"""Buddy's local brain: understands typed prompts and turns them into actions.

No internet, no account, no model download. Intents are matched with clear
patterns, so behaviour is predictable and testable. Anything it cannot do is
answered honestly instead of faked.
"""
import csv
import os
import re
import webbrowser
from datetime import datetime

from docs import (append_to_document, build_document, read_document_blocks,
                  text_to_blocks)
from llm import ask_ai, describe_backend
from office import build_presentation, build_spreadsheet, read_pdf_text
from tools import (ToolError, check_python, clean_csv, clipboard_copy,
                   clipboard_history, clipboard_paste, copy_file, create_file,
                   create_folder, delete_file, do_bulk_rename, download_file,
                   file_info, file_stats, find_duplicates, find_large_files,
                   find_rename_matches, find_temp_files, git_branch, git_commit,
                   git_info, http_get, image_to_pdf, list_files, load_facts,
                   load_notes, load_settings, load_work_log, log_work,
                   media_convert, move_file, ocr_image, open_app,
                   open_app_with_file, open_file, pdf_merge, pdf_split,
                   pivot_csv, power_action, read_any, read_calendar_file,
                   read_email_file, read_file, rename_file, recent_files,
                   redact_file, research_topic, resolve_path, run_python,
                   run_script, safe_calculate, save_fact, save_note,
                   save_settings, scrape_text, search_files, set_brightness,
                   speak, sqlite_select, startup_add, startup_remove,
                   system_info, take_screenshot, web_search, wifi_toggle,
                   write_csv)

PET_COLORS = {
    "yellow": "#FFD66B", "pink": "#FFB3C7", "blue": "#A8D8FF",
    "green": "#B5E6A2", "purple": "#D9C2FF", "orange": "#FFC98A",
    "mint": "#B5E6A2", "gold": "#FFD66B",
}

# Cloud entry points: these open in the browser, signed in as the user.
WEB_APPS = {
    "copilot": "https://copilot.microsoft.com",
    "office 365": "https://www.office.com",
    "microsoft 365": "https://www.office.com",
    "office": "https://www.office.com",
    "onedrive": "https://onedrive.live.com",
    "teams": "https://teams.microsoft.com",
    "outlook mail": "https://outlook.live.com",
    "outlook web": "https://outlook.live.com",
}

JOKES = [
    "Why did the computer go to the doctor? Because it had a virus!",
    "I told my computer I needed a break... now it won't stop sending me KitKat ads.",
    "Why do programmers prefer dark mode? Because light attracts bugs!",
]

HELP_TEXT = """Here's what I can do for you:
- Chat: hello, how are you, tell me a joke, my name is ...
- Open: open notepad / calculator / paint / browser / open file report.docx
- Files: list files in Documents | read myfile.txt | create file todo.txt with Buy milk
- Find: search files for birthday in Documents
- Organise: copy a.txt to b.txt | move a.txt to Documents | rename a.txt to b.txt
- Folders: create folder Photos | recent files in Documents | file info report.docx
- Delete (always asks first): delete old.txt
- Documents: create document Report.docx title "My Report" heading "Intro" paragraph "Hello world" bullet "First point"
- Add more: add to document Report.docx paragraph "Another paragraph"
- Read anything: read document Report.docx (works for txt, docx, csv, json)
- Convert: convert notes.txt to docx
- Spreadsheets: create spreadsheet Data.csv headers "Name,Age" rows "Asha,20" "Ravi,21"
- Summarise: summarize file notes.txt
- Notes: note: Call Amma at 6 | show notes
- Reminders: remind me in 10 minutes to drink water
- Maths: calculate 12 * 8 + 5
- Time & date: what time is it | what is today's date
- Computer: system info
- Web (needs internet): search the web for cute cats
- Settings: set pet name to Max | set pet color to blue | set greeting to "Hey boss!" | set chat font size to 14 | show settings | reset settings
- Office: create excel Data.xlsx headers "Name,Score" rows "Asha,90" "Ravi,80" (values starting with = become formulas) | convert data.csv to excel | create presentation Deck.pptx title "Report" slides "Intro" "Point one" "Point two" ; "Next" "More"
- Summaries: summarize document Report.docx | read pdf Manual.pdf
- Bulk & cleanup: bulk rename in Photos "IMG_" to "Trip_" (asks first) | large files in Downloads | duplicate files in Documents | temp files in Downloads
- Data: clean csv data.csv | pivot data.csv by Department sum Salary
- Code & data: run python script.py | check python script.py | git status in myproject | query database shop.db SELECT name FROM products | http get example.com
- Workflows: create file a.txt with hello then copy a.txt to b.txt
 - Pets: be a cat | be a puppy | be a robot | be a spirit | be a muse | be a real cat | be a real dog | be a real kitty | set pet size to 200 | set move speed to fast | turn voice on/off | set voice volume to 80 | autonomy on/off | confirmation mode strict | say hello | show settings page
- Web: download <url> to Downloads | scrape <url> | research <topic>
- Mail & calendar files: read email saved.eml | read calendar holidays.ics
- Code & Git: run script x.py | git commit in folder message "msg" | git branch in folder name
- OS: wifi on/off | brightness 70 | sleep/shutdown/restart computer (asks first)
- AI (needs Ollama/LM Studio in Settings): ask ai <question> | ai status | set ai backend to ollama | set ai model to llama3
- Memory: remember that my favourite colour is blue | what do you remember | recent work
- Privacy: redact file notes.txt words "password,secret"
- Clipboard: copy hello world to clipboard | show clipboard | clipboard history
- Screenshot: take screenshot (needs Pillow: pip install pillow)
- Apps: open word / excel / powerpoint / outlook / onenote / vscode / spotify / whatsapp / zoom / vlc / firefox (any installed app works by name) | open file Report.docx (opens in its default app, e.g. Word) | open word with Report.docx
- Microsoft 365 & Copilot: open copilot | open office 365 | open onedrive | open teams | ask copilot what is a pivot table (opens Copilot and copies your question — paste it there)
- OneDrive files: list files in onedrive | read onedrive/notes.txt (works when OneDrive syncs to your PC)
- Startup: start with windows | stop starting with windows
 - Pets: be a cat | be a puppy | be a robot | be a spirit | be a muse | be a real cat | be a real dog | be a real kitty (change in the settings page too)
- Voice: say hello there | turn voice on | turn voice off (mic button in the chat box listens)
- Wander: autonomy on | autonomy off (Buddy strolls, hides and plays on its own)"""


def parse_segments(text):
    """Parse: title "X" heading "Y" paragraph "Z" bullet "W" ... in order."""
    return [(kind, value) for kind, value in
            re.findall(r'(title|heading|paragraph|bullet)\s+"([^"]+)"', text)]


def _cell_value(text):
    """CSV text -> number, formula (kept as-is), or plain string."""
    if text.startswith("="):
        return text
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def split_chain(text):
    """Split 'do this then do that' on ' then ' outside quoted strings."""
    parts, current, in_quote = [], [], False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"':
            in_quote = not in_quote
            current.append(ch)
            i += 1
        elif not in_quote and text[i:i + 6].lower() == " then ":
            parts.append("".join(current).strip())
            current = []
            i += 6
        else:
            current.append(ch)
            i += 1
    parts.append("".join(current).strip())
    return [p for p in parts if p]


class Brain:
    def __init__(self, launcher=None, opener=None, reminders=None):
        self.launcher = launcher      # injected app launcher (tests)
        self.opener = opener          # injected browser opener (tests)
        self.reminders = reminders    # ReminderService (UI wires popups)
        self.pending = None           # ("delete", path) or ("bulk", ...) awaiting yes/no
        self.user_name = None
        self.on_reminder = None       # UI sets this to show a popup
        self.settings_changed = {}    # UI reads this after each reply

    # -- helpers ------------------------------------------------------
    def _name(self):
        return f", {self.user_name}" if self.user_name else ""

    def _strict(self):
        """Strict confirmation mode: ask before scripts, overwrites, power."""
        return load_settings().get("confirm_mode") == "strict"

    def _save_setting(self, key, value):
        settings = load_settings()
        settings[key] = value
        save_settings(settings)

    # -- main entry ---------------------------------------------------
    def handle(self, text):
        """Return (reply, mood). Moods: idle, happy, thinking, sad, love."""
        raw = text or ""
        msg = raw.strip()
        low = msg.lower()
        self.settings_changed = {}

        # 0. Multi-step workflows: "do this then do that then do the other".
        parts = split_chain(msg)
        if len(parts) > 1:
            replies, merged, moods = [], {}, []
            for part in parts:
                reply, mood = self.handle(part)
                replies.append(reply)
                moods.append(mood)
                merged.update(self.settings_changed)
            self.settings_changed = merged
            # A finished multi-step workflow celebrates; a roadblock or a
            # pending approval wins over the celebration.
            if "error" in moods:
                final = "error"
            elif "waiting" in moods:
                final = "waiting"
            elif "sad" in moods:
                final = "sad"
            else:
                final = "celebrating"
            return "\n".join(replies), final

        # 1. Confirmations for a pending action come first. This is the
        # human-in-the-loop approval gate: destructive or irreversible
        # actions never run until the user says yes (in chat, or via the
        # approval popup the UI shows for "waiting" replies).
        if self.pending is not None:
            if low in ("yes", "yeah", "confirm", "yes delete", "delete it",
                       "yes do it"):
                kind = self.pending[0]
                data = self.pending[1:]
                self.pending = None
                if kind == "delete":
                    try:
                        delete_file(data[0])
                        return f"Deleted {data[0]}.", "sad"
                    except ToolError as e:
                        return str(e), "sad"
                if kind == "bulk":
                    folder, matches = data
                    done, failed = do_bulk_rename(folder, matches)
                    reply = f"Renamed {len(done)} files."
                    if failed:
                        reply += (f" {len(failed)} failed: " +
                                  ", ".join(f"{n} ({e})" for n, e in failed[:3]))
                    return reply, "happy"
                if kind == "run":
                    try:
                        code, out, err = run_script(data[0])
                        reply = f"Exit code {code}."
                        if out:
                            reply += f"\nOutput:\n{out}"
                        if err:
                            reply += f"\nErrors:\n{err}"
                        return reply, "celebrating" if code == 0 else "error"
                    except ToolError as e:
                        return str(e), "error"
                if kind == "overwrite":
                    path, content = data
                    try:
                        create_file(path, content)
                        return f"Overwrote {path}.", "celebrating"
                    except ToolError as e:
                        return str(e), "sad"
                if kind == "power":
                    try:
                        return power_action(data[0]), "sad"
                    except ToolError as e:
                        return str(e), "sad"
            if low in ("no", "cancel", "never mind", "don't"):
                kind = self.pending[0]
                self.pending = None
                if kind == "delete":
                    return "Okay, I won't delete it. Phew!", "happy"
                if kind == "power":
                    return "Okay, not touching the power. Phew!", "happy"
                if kind == "run":
                    return "Okay, I won't run it.", "happy"
                if kind == "overwrite":
                    return "Okay, leaving the existing file alone.", "happy"
                return "Okay, nothing renamed.", "happy"
            # Anything else: cancel the pending action, handle the message.
            self.pending = None

        # 2. Remembering the user's name.
        m = re.match(r"my name is ([A-Za-z][A-Za-z .'-]{0,40})$", low)
        if m:
            self.user_name = m.group(1).strip().title()
            return f"Nice to meet you{self._name()}! I'll remember that.", "love"

        # 3. Small talk.
        if re.match(r"^(hi+|hello|hey|hii+|good (morning|afternoon|evening))\b", low):
            return f"Hello{self._name()}! How can I help you today?", "happy"
        if "how are you" in low:
            return ("I'm doing great, thank you! Sitting here on your desktop, "
                    "ready whenever you need me."), "happy"
        if "thank" in low:
            return "You're very welcome! Anything else I can do?", "love"
        if re.search(r"\b(bye|goodbye|see you)\b", low):
            return "Bye! I'll be right here when you need me.", "happy"
        if "your name" in low or "who are you" in low:
            return ("I'm Buddy, your little desktop pet! I live on your computer, "
                    "work completely offline, and love helping with small tasks."), "happy"
        if "joke" in low:
            import random
            return random.choice(JOKES), "happy"
        # (Pet compliments live just before the fallback, so they never
        # hijack a real command like "search the web for cute cats".)
        if low in ("help", "what can you do", "commands", "menu"):
            return HELP_TEXT, "idle"

        # 4. Time and date.
        if "time" in low:
            return f"It's {datetime.now().strftime('%I:%M %p')}.", "idle"
        if "date" in low or "today" in low:
            return f"Today is {datetime.now().strftime('%A, %d %B %Y')}.", "idle"

        # 5. Calculator.
        m = re.match(r"^(calculate|calc|compute|what is|what's)\s+(.+)$", low)
        expr = None
        if m:
            expr = m.group(2)
        elif re.fullmatch(r"[\d\s.+\-*/%()]+", low) and re.search(r"\d", low) \
                and re.search(r"[+\-*/%]", low):
            expr = low
        if expr is not None:
            try:
                result = safe_calculate(expr)
                return f"{expr.strip()} = {result}", "happy"
            except ToolError as e:
                return str(e), "sad"

        # 6. Reminders.
        m = re.match(r"remind me in (\d+) (second|seconds|minute|minutes|hour|hours) to (.+)$", low)
        if m:
            amount, unit, what = int(m.group(1)), m.group(2), m.group(3)
            seconds = amount * {"second": 1, "seconds": 1, "minute": 60,
                                "minutes": 60, "hour": 3600, "hours": 3600}[unit]
            if self.reminders is not None:
                callback = self.on_reminder or self._reminder_fired
                self.reminders.remind_in(seconds, what, callback)
            return (f"Got it! I'll remind you in {amount} {unit} to {what}."), "happy"

        # 7. Web search (opens the browser; needs internet for results).
        m = re.match(r"^(search (the )?web for|google|search)\s+(.+)$", low)
        if m:
            query = m.group(3)
            web_search(query, opener=self.opener)
            return (f"Opening a web search for '{query}' in your browser. "
                    "You'll need an internet connection for the results."), "happy"

        # 7b. Documents, spreadsheets and file powers (case preserved).
        m = re.match(r'^create document (\S+)\s*(.*)$', msg, re.IGNORECASE)
        if m:
            fname, rest = m.group(1), m.group(2)
            if not fname.lower().endswith(".docx"):
                fname += ".docx"
            segments = parse_segments(rest)
            if not segments:
                return ("Tell me what to put in it, like: create document Report.docx "
                        'title "My Report" heading "Intro" paragraph "Hello world" '
                        'bullet "First point"'), "thinking"
            try:
                path = build_document(segments, resolve_path(fname))
                log_work("create document", path)
                return f"Created your Word document: {path}.", "celebrating"
            except (ToolError, OSError) as e:
                return f"I couldn't write that document: {e}.", "sad"

        m = re.match(r'^add to document (\S+)\s+(.*)$', msg, re.IGNORECASE)
        if m:
            fname, rest = m.group(1), m.group(2)
            segments = parse_segments(rest)
            if not segments:
                return ('Tell me what to add, like: add to document Report.docx '
                        'paragraph "Another paragraph"'), "thinking"
            try:
                path = append_to_document(resolve_path(fname), segments)
                return f"Added to {path}.", "happy"
            except (ToolError, OSError) as e:
                return f"I couldn't update that document: {e}.", "sad"

        m = re.match(r'^convert (\S+) to docx$', msg, re.IGNORECASE)
        if m:
            src = m.group(1)
            if src.lower().endswith(".docx"):
                return "That's already a Word document!", "idle"
            try:
                text = read_any(src)
                base = resolve_path(src)
                dest = (os.path.splitext(base)[0] + ".docx")
                build_document(text_to_blocks(text), dest)
                return f"Converted to {dest}.", "celebrating"
            except (ToolError, OSError) as e:
                return f"I couldn't convert that: {e}.", "sad"

        m = re.match(r'^create spreadsheet (\S+)\s+headers\s+"([^"]+)"\s+rows\s+(.*)$',
                     msg, re.IGNORECASE)
        if m:
            fname, headers_s, rows_s = m.group(1), m.group(2), m.group(3)
            if not fname.lower().endswith(".csv"):
                fname += ".csv"
            headers = [h.strip() for h in headers_s.split(",")]
            rows = [[c.strip() for c in row.split(",")]
                    for row in re.findall(r'"([^"]+)"', rows_s)]
            try:
                from tools import write_csv
                path = write_csv(resolve_path(fname), headers, rows)
                log_work("create spreadsheet", path)
                return f"Created your spreadsheet: {path} ({len(rows)} rows).", "celebrating"
            except (ToolError, OSError) as e:
                return f"I couldn't write that spreadsheet: {e}.", "sad"

        m = re.match(r'^read document (.+)$', msg, re.IGNORECASE)
        if m:
            try:
                content = read_any(m.group(1))
                shown = content if len(content) <= 2000 else content[:2000] + "\n... (cut off)"
                return f"Here's {m.group(1)}:\n{shown}", "idle"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^open file (.+)$', msg, re.IGNORECASE)
        if m:
            try:
                path = open_file(m.group(1), launcher=self.launcher)
                return f"Opening {path}...", "happy"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^copy (.+?) to (.+)$', msg, re.IGNORECASE)
        if m and m.group(2).strip().lower() != "clipboard":
            try:
                dest = copy_file(m.group(1), m.group(2))
                return f"Copied to {dest}.", "happy"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^move (.+?) to (.+)$', msg, re.IGNORECASE)
        if m:
            try:
                dest = move_file(m.group(1), m.group(2))
                return f"Moved to {dest}.", "happy"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^rename (.+?) to (.+)$', msg, re.IGNORECASE)
        if m:
            try:
                dest = rename_file(m.group(1), m.group(2))
                return f"Renamed to {dest}.", "happy"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^create folder (.+)$', msg, re.IGNORECASE)
        if m:
            try:
                path = create_folder(m.group(1))
                return f"Created the folder {path}.", "happy"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^file info (.+)$', msg, re.IGNORECASE)
        if m:
            try:
                info = file_info(m.group(1))
                return (f"{info['path']}\nType: {info['kind']}\n"
                        f"Size: {info['size_bytes']} bytes\n"
                        f"Modified: {info['modified']}"), "idle"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^recent files( in (.+))?$', msg, re.IGNORECASE)
        if m:
            try:
                names = recent_files(m.group(2))
                if not names:
                    return "No files in that folder.", "idle"
                return "Most recent files:\n" + "\n".join(names), "idle"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^summarize file (.+)$', msg, re.IGNORECASE)
        if m:
            try:
                stats = file_stats(m.group(1))
                first = [ln for ln in stats["text"].splitlines() if ln.strip()][:3]
                preview = "\n".join(first)
                return (f"Summary of {m.group(1)}: {stats['lines']} lines, "
                        f"{stats['words']} words, {stats['chars']} characters.\n"
                        f"Starts with:\n{preview}"), "idle"
            except ToolError as e:
                return str(e), "sad"

        # 7c. Settings.
        m = re.match(r'^(set pet name to|call yourself)\s+(.+)$', msg, re.IGNORECASE)
        if m:
            name = m.group(2).strip().strip('"').title()
            self._save_setting("pet_name", name)
            self.settings_changed["pet_name"] = name
            return f"From now on, call me {name}!", "love"

        m = re.match(r'^set pet color to (\w+)$', low)
        if m:
            color = m.group(1)
            if color not in PET_COLORS:
                return ("I come in these colours: " + ", ".join(sorted(PET_COLORS)) + "."), "thinking"
            self._save_setting("pet_color", PET_COLORS[color])
            self._save_setting("pet_color_name", color)
            self.settings_changed["pet_color"] = PET_COLORS[color]
            return f"Love it! I'm {color} now.", "happy"

        m = re.match(r'^set greeting to "([^"]+)"$', msg, re.IGNORECASE)
        if m:
            self._save_setting("greeting", m.group(1))
            self.settings_changed["greeting"] = m.group(1)
            return f"Got it — I'll greet you with: {m.group(1)}", "happy"

        m = re.match(r'^set chat font size to (\d+)$', low)
        if m:
            size = max(10, min(20, int(m.group(1))))
            self._save_setting("chat_font", size)
            self.settings_changed["chat_font"] = size
            return f"Chat text size set to {size}.", "happy"

        if low == "show settings":
            settings = load_settings()
            lines = [
                f"Pet name: {settings.get('pet_name', 'Buddy')}",
                f"Pet type: {settings.get('pet_species', 'real_cat')}",
                f"Pet size: {settings.get('pet_size', 180)}",
                f"Move speed: {settings.get('move_speed', 'normal')}",
                f"Pet colour: {settings.get('pet_color_name', 'yellow')}",
                f"Greeting: {settings.get('greeting', 'default')}",
                f"Chat font size: {settings.get('chat_font', 11)}",
                f"Voice: {'on' if settings.get('voice', True) else 'off'}",
                f"Voice volume: {settings.get('voice_volume', 100)}",
                f"Wander & play on its own: {'on' if settings.get('autonomy', True) else 'off'}",
                f"Confirmation mode: {settings.get('confirm_mode', 'standard')}",
                f"AI backend: {settings.get('llm_backend', 'off')}"
                f" ({settings.get('llm_model', 'no model')})",
                f"Your name: {self.user_name or 'not set yet'}",
            ]
            return "Your settings:\n" + "\n".join(lines), "idle"

        if low == "reset settings":
            save_settings({})
            self.settings_changed = {"pet_name": "Buddy",
                                     "pet_color": PET_COLORS["yellow"],
                                     "chat_font": 11, "greeting": None,
                                     "pet_species": "real_cat", "voice": True,
                                     "autonomy": True, "pet_size": 180,
                                     "move_speed": "normal",
                                     "confirm_mode": "standard",
                                     "voice_volume": 100}
            return "Settings reset to the defaults.", "idle"

        m = re.match(r"^(be a|set pet to|change pet to|i want a)\s+"
                     r"(cat|puppy|blob|robot|spirit|muse|real cat|real dog|real kitty)$", low)
        if m:
            species = m.group(2).replace(" ", "_")
            self._save_setting("pet_species", species)
            self.settings_changed["pet_species"] = species
            names = {"cat": "a cat", "puppy": "a puppy", "blob": "a blob",
                     "robot": "a robot", "spirit": "a spirit",
                     "muse": "a Muse-style AI pet",
                     "real_cat": "a real orange cat",
                     "real_dog": "a real border collie",
                     "real_kitty": "a real grey kitty"}
            return f"Poof! I'm {names[species]} now.", "happy"

        m = re.match(r"^set pet size to (\d+)$", low)
        if m:
            size = max(120, min(280, int(m.group(1))))
            self._save_setting("pet_size", size)
            self.settings_changed["pet_size"] = size
            return f"Pet size set to {size}.", "happy"

        m = re.match(r"^set move speed to (slow|normal|fast)$", low)
        if m:
            self._save_setting("move_speed", m.group(1))
            self.settings_changed["move_speed"] = m.group(1)
            return f"Move speed set to {m.group(1)}.", "happy"

        m = re.match(r"^confirmation mode (strict|standard)$", low)
        if m:
            self._save_setting("confirm_mode", m.group(1))
            self.settings_changed["confirm_mode"] = m.group(1)
            if m.group(1) == "strict":
                return ("Strict mode on: I'll ask before running scripts, "
                        "overwriting files, and power actions — on top of "
                        "the usual delete/rename approvals."), "happy"
            return "Standard mode: I ask before deletes and renames.", "happy"

        m = re.match(r"^set voice volume to (\d+)$", low)
        if m:
            vol = max(0, min(100, int(m.group(1))))
            self._save_setting("voice_volume", vol)
            self.settings_changed["voice_volume"] = vol
            return f"Voice volume set to {vol}.", "happy"

        m = re.match(r"^(turn voice|voice)\s+(on|off)$", low)
        if m:
            on = m.group(2) == "on"
            self._save_setting("voice", on)
            self.settings_changed["voice"] = on
            return ("My voice is on — I'll speak my replies aloud." if on
                    else "Voice off — I'll stay quiet and just write."), "happy"

        m = re.match(r"^(turn autonomy|autonomy)\s+(on|off)$", low)
        if m:
            on = m.group(2) == "on"
            self._save_setting("autonomy", on)
            self.settings_changed["autonomy"] = on
            return ("I'll wander, hide and play on the desktop on my own." if on
                    else "Okay — I'll stay put until you move me."), "happy"

        if low in ("settings", "open settings", "show settings page"):
            self.settings_changed["open_settings"] = True
            return "Opening the settings page...", "idle"

        m = re.match(r"^say (.+)$", msg, re.IGNORECASE)
        if m:
            try:
                from tools import set_voice_volume
                set_voice_volume(load_settings().get("voice_volume", 100))
                speak(m.group(1))
                return f"Speaking: {m.group(1)[:100]}", "speaking"
            except ToolError as e:
                return str(e), "sad"

        # 7d. Office, data, code, and power tools.
        m = re.match(r'^create excel (\S+)\s+headers\s+"([^"]+)"\s+rows\s+(.*)$',
                     msg, re.IGNORECASE)
        if m:
            fname, headers_s, rows_s = m.group(1), m.group(2), m.group(3)
            if not fname.lower().endswith(".xlsx"):
                fname += ".xlsx"
            headers = [h.strip() for h in headers_s.split(",")]
            rows = [[c.strip() for c in row.split(",")]
                    for row in re.findall(r'"([^"]+)"', rows_s)]
            rows = [[_cell_value(c) for c in row] for row in rows]
            try:
                path = build_spreadsheet(headers, rows, resolve_path(fname))
                log_work("create excel", path)
                return f"Created your Excel file: {path} ({len(rows)} rows).", "celebrating"
            except OSError as e:
                return f"I couldn't write that spreadsheet: {e}.", "sad"

        m = re.match(r'^create presentation (\S+)\s+title\s+"([^"]+)"\s+slides\s+(.*)$',
                     msg, re.IGNORECASE)
        if m:
            fname, title, slides_s = m.group(1), m.group(2), m.group(3)
            if not fname.lower().endswith(".pptx"):
                fname += ".pptx"
            slides = [(title, [])]
            for chunk in slides_s.split(";"):
                qs = re.findall(r'"([^"]+)"', chunk)
                if qs:
                    slides.append((qs[0], qs[1:]))
            try:
                path = build_presentation(slides, resolve_path(fname))
                log_work("create presentation", path)
                return f"Created your presentation: {path} ({len(slides)} slides).", "celebrating"
            except OSError as e:
                return f"I couldn't write that presentation: {e}.", "sad"

        m = re.match(r'^convert (\S+) to excel$', msg, re.IGNORECASE)
        if m:
            src = m.group(1)
            try:
                with open(resolve_path(src), "r", encoding="utf-8", newline="") as f:
                    rows = list(csv.reader(f))
                if not rows:
                    return "That file is empty.", "thinking"
                headers, data = rows[0], [[_cell_value(c) for c in r] for r in rows[1:]]
                base = os.path.splitext(resolve_path(src))[0] + ".xlsx"
                build_spreadsheet(headers, data, base)
                return f"Converted to {base}.", "celebrating"
            except (ToolError, OSError) as e:
                return f"I couldn't convert that: {e}.", "sad"

        m = re.match(r'^convert (\S+) to txt$', msg, re.IGNORECASE)
        if m:
            src = m.group(1)
            try:
                text = read_any(src)
                base = os.path.splitext(resolve_path(src))[0] + ".txt"
                create_file(base, text)
                return f"Converted to {base}.", "celebrating"
            except (ToolError, OSError) as e:
                return f"I couldn't convert that: {e}.", "sad"

        m = re.match(r'^summarize document (.+)$', msg, re.IGNORECASE)
        if m:
            try:
                path = resolve_path(m.group(1))
                if path.lower().endswith(".docx"):
                    blocks = read_document_blocks(path)
                    headings = [t for k, t in blocks if k in ("title", "heading")]
                    text = "\n".join(t for _, t in blocks)
                else:
                    headings, text = [], read_any(m.group(1))
                words = len(text.split())
                first = next((ln for ln in text.splitlines() if ln.strip()), "")
                reply = f"Summary of {m.group(1)}: {words} words."
                if headings:
                    reply += "\nSections: " + ", ".join(headings[:10])
                reply += f"\nStarts with: {first[:200]}"
                return reply, "idle"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^read pdf (.+)$', msg, re.IGNORECASE)
        if m:
            try:
                text = read_pdf_text(resolve_path(m.group(1)))
                shown = text if len(text) <= 2000 else text[:2000] + "\n... (cut off)"
                return f"Here's {m.group(1)}:\n{shown}", "idle"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^bulk rename in (.+?)\s+"([^"]+)"\s+to\s+"([^"]+)"$',
                     msg, re.IGNORECASE)
        if m:
            try:
                matches = find_rename_matches(m.group(1), m.group(2), m.group(3))
            except ToolError as e:
                return str(e), "sad"
            if not matches:
                return f"No file names in that folder contain '{m.group(2)}'.", "idle"
            self.pending = ("bulk", resolve_path(m.group(1)), matches)
            preview = "\n".join(f"{a} -> {b}" for a, b in matches[:10])
            if len(matches) > 10:
                preview += f"\n... and {len(matches) - 10} more"
            return (f"Found {len(matches)} files to rename:\n{preview}\n"
                    f"Reply 'yes' to rename them all."), "waiting"

        m = re.match(r'^large files( in (.+))?$', msg, re.IGNORECASE)
        if m:
            try:
                found = find_large_files(m.group(2))
            except ToolError as e:
                return str(e), "sad"
            if not found:
                return "No files found there.", "idle"
            lines = [f"{size / 1_048_576:.1f} MB — {path}" for size, path in found]
            return "Largest files:\n" + "\n".join(lines), "idle"

        m = re.match(r'^duplicate files( in (.+))?$', msg, re.IGNORECASE)
        if m:
            try:
                groups = find_duplicates(m.group(2))
            except ToolError as e:
                return str(e), "sad"
            if not groups:
                return "No duplicate files found. Nice and tidy!", "happy"
            out = [f"Duplicate set ({len(g)} copies):\n" + "\n".join(g) for g in groups[:10]]
            return "\n\n".join(out), "idle"

        m = re.match(r'^temp files( in (.+))?$', msg, re.IGNORECASE)
        if m:
            try:
                hits = find_temp_files(m.group(2))
            except ToolError as e:
                return str(e), "sad"
            if not hits:
                return "No temporary files found.", "idle"
            return (f"Found {len(hits)} temporary files:\n" +
                    "\n".join(hits[:20]) +
                    ("\n... (showing 20)" if len(hits) > 20 else "")), "idle"

        m = re.match(r'^clean csv (\S+)(?: to (\S+))?$', msg, re.IGNORECASE)
        if m:
            try:
                dest, before, after = clean_csv(m.group(1), m.group(2))
                return (f"Cleaned: {before} rows in, {after} rows out "
                        f"(empty rows and duplicates removed).\nSaved to {dest}."), "happy"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^pivot (\S+) by (\S+)(?: sum (\S+))?$', msg, re.IGNORECASE)
        if m:
            try:
                groups = pivot_csv(m.group(1), m.group(2), m.group(3))
            except ToolError as e:
                return str(e), "sad"
            if not groups:
                return "Nothing to group in that file.", "idle"
            biggest = max(g["count"] for g in groups.values())
            lines = []
            for key, g in sorted(groups.items(), key=lambda kv: -kv[1]["count"]):
                bar = "#" * max(1, int(g["count"] / biggest * 20)) if biggest else ""
                line = f"{key or '(blank)'}: {g['count']}  {bar}"
                if m.group(3):
                    line += f"  (sum {m.group(3)}: {g['sum']:g})"
                lines.append(line)
            return "Grouped by " + m.group(2) + ":\n" + "\n".join(lines), "idle"

        m = re.match(r'^run python (\S+)$', msg, re.IGNORECASE)
        if m:
            if self._strict():
                self.pending = ("run", resolve_path(m.group(1)))
                return (f"Strict mode: run {m.group(1)}? "
                        "Reply 'yes' to run it or 'no' to cancel."), "waiting"
            try:
                code, out, err = run_python(m.group(1))
                reply = f"Exit code {code}."
                if out:
                    reply += f"\nOutput:\n{out}"
                if err:
                    reply += f"\nErrors:\n{err}"
                return reply, "celebrating" if code == 0 else "error"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^check python (\S+)$', msg, re.IGNORECASE)
        if m:
            try:
                check_python(m.group(1))
                return "That Python file has no syntax errors.", "celebrating"
            except ToolError as e:
                return str(e), "error"

        m = re.match(r'^git (status|log)(?: in (.+))?$', msg, re.IGNORECASE)
        if m:
            try:
                return git_info(m.group(2), m.group(1)), "idle"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^query database (\S+) (.+)$', msg, re.IGNORECASE)
        if m:
            try:
                columns, rows = sqlite_select(m.group(1), m.group(2))
            except ToolError as e:
                return str(e), "sad"
            if not rows:
                return "The query ran but returned no rows.", "idle"
            header = " | ".join(columns)
            lines = [header] + [" | ".join(str(c) for c in row) for row in rows]
            if len(rows) == 100:
                lines.append("(showing first 100 rows)")
            return "\n".join(lines), "idle"

        m = re.match(r'^http get (\S+)$', msg, re.IGNORECASE)
        if m:
            try:
                status, text = http_get(m.group(1))
                return f"Status {status}:\n{text[:1000]}", "idle"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^remember that (.+)$', msg, re.IGNORECASE)
        if m:
            count = save_fact(m.group(1))
            return f"Remembered. I now hold {count} facts about you.", "love"

        if low == "what do you remember":
            facts = load_facts()
            if not facts:
                return "Nothing yet — say 'remember that ...' to teach me.", "idle"
            lines = [f"- {f['text']} ({f.get('time', '')})" for f in facts[-20:]]
            return "What I remember:\n" + "\n".join(lines), "idle"

        m = re.match(r'^redact file (\S+) words "([^"]+)"$', msg, re.IGNORECASE)
        if m:
            try:
                dest, total = redact_file(m.group(1),
                                          [w for w in m.group(2).split(",")])
                return (f"Redacted {total} occurrences into {dest}. "
                        f"Your original is untouched."), "happy"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^copy (.+?) to clipboard$', msg, re.IGNORECASE)
        if m:
            clipboard_copy(m.group(1))
            return f"Copied to your clipboard: {m.group(1)[:100]}", "happy"

        if low == "show clipboard":
            text = clipboard_paste()
            return (f"Clipboard holds: {text}" if text else
                    "Your clipboard is empty (or I can't read it)."), "idle"

        if low == "clipboard history":
            history = clipboard_history()
            if not history:
                return "Nothing copied through me yet.", "idle"
            return "Recent copies:\n" + "\n".join(history[-10:]), "idle"

        if low == "take screenshot":
            try:
                path = take_screenshot()
                return f"Screenshot saved to {path}.", "happy"
            except ToolError as e:
                return str(e), "sad"

        if low in ("start with windows", "add to startup"):
            try:
                link = startup_add()
                return f"Done — Buddy will start with Windows ({link}).", "happy"
            except ToolError as e:
                return str(e), "sad"

        if low in ("stop starting with windows", "remove from startup"):
            try:
                removed = startup_remove()
                return ("Buddy will no longer start with Windows." if removed
                        else "Buddy wasn't set to start with Windows."), "happy"
            except ToolError as e:
                return str(e), "sad"

        # 8. Open apps: desktop apps, Office 365 web apps, Copilot.
        m = re.match(r"^open (.+?) with (.+)$", msg, re.IGNORECASE)
        if m:
            app, fname = m.group(1).strip(), m.group(2).strip()
            try:
                open_app_with_file(app, fname, launcher=self.launcher)
                return f"Opening {fname} in {app}...", "happy"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^ask copilot (.+)$", msg, re.IGNORECASE)
        if m:
            question = m.group(1).strip()
            clipboard_copy(question)
            url = WEB_APPS["copilot"]
            if self.opener is not None:
                self.opener(url)
            else:
                webbrowser.open(url)
            return ("Copilot is opening in your browser, and I've copied your "
                    f"question to the clipboard — just paste it there:\n{question}"), "happy"

        m = re.match(r"^open (.+)$", low)
        if m:
            app = m.group(1).strip()
            if app in WEB_APPS:
                url = WEB_APPS[app]
                if self.opener is not None:
                    self.opener(url)
                else:
                    webbrowser.open(url)
                return f"Opening {app} in your browser...", "happy"
            try:
                open_app(app, launcher=self.launcher)
                return f"Opening {app}...", "happy"
            except ToolError as e:
                return str(e), "sad"

        # 9. List files.
        m = re.match(r"^(list|show) files( in (.+))?$", low)
        if m:
            try:
                reply, _ = list_files(m.group(3) or "~")
                return reply, "idle"
            except ToolError as e:
                return str(e), "sad"

        # 10. Read a file (any type: txt, docx, csv, json...).
        m = re.match(r"^read (file )?(.+)$", low)
        if m:
            try:
                content = read_any(m.group(2))
                shown = content if len(content) <= 2000 else content[:2000] + "\n... (cut off)"
                return f"Here's {m.group(2)}:\n{shown}", "idle"
            except ToolError as e:
                return str(e), "sad"

        # 11. Create a file.
        m = re.match(r"^create file (.+?)(?:\s+(?:with|containing|:)\s+(.+))?$", low)
        if m:
            content = m.group(2) or ""
            if self._strict() and os.path.isfile(resolve_path(m.group(1))):
                self.pending = ("overwrite", m.group(1), content)
                return (f"Strict mode: {m.group(1)} already exists. "
                        "Overwrite it? Reply 'yes' or 'no'."), "waiting"
            try:
                path = create_file(m.group(1), content)
                log_work("create file", path)
                return f"Created {path}.", "happy"
            except ToolError as e:
                return str(e), "sad"

        # 12. Search inside files.
        m = re.match(r"^(search|find) files (for|containing) (.+?)(?: in (.+))?$", low)
        if m:
            try:
                hits = search_files(m.group(3), m.group(4))
                if not hits:
                    return f"I didn't find '{m.group(3)}' in any text files there.", "idle"
                return "I found it in:\n" + "\n".join(hits), "happy"
            except ToolError as e:
                return str(e), "sad"

        # 13. Delete (two-step confirmation).
        m = re.match(r"^delete (file )?(.+)$", low)
        if m:
            self.pending = ("delete", m.group(2))
            return (f"Are you sure you want to delete {m.group(2)}? "
                    "Reply 'yes' to confirm or 'no' to cancel."), "waiting"

        # 14. Notes.
        m = re.match(r"^(note|remember)( that)?:?\s+(.+)$", low)
        if m:
            count = save_note(m.group(3))
            return f"Noted! That's note number {count}.", "happy"
        if re.match(r"^(show|list)( my)? notes$", low):
            notes = load_notes()
            if not notes:
                return "You have no notes yet. Say 'note: ...' to add one.", "idle"
            lines = [f"{i+1}. {n['text']} ({n['time']})"
                     for i, n in enumerate(notes[-20:])]
            return "Your notes:\n" + "\n".join(lines), "idle"

        # 15. System info.
        if re.match(r"^(system info|about (my )?(computer|pc|system))$", low):
            info = system_info()
            lines = [f"{k}: {v}" for k, v in info.items()]
            return "Here's your computer:\n" + "\n".join(lines), "idle"

        # 7e. Web downloads, research, local mail/calendar, git, OS control,
        # and the optional AI backend.
        m = re.match(r"^download (.+?)(?: to (.+))?$", msg, re.IGNORECASE)
        if m:
            try:
                dest = download_file(m.group(1), m.group(2))
                log_work("download", dest)
                return f"Downloaded to {dest}.", "celebrating"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^scrape (.+)$", msg, re.IGNORECASE)
        if m:
            try:
                return scrape_text(m.group(1)), "idle"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^research (.+)$", msg, re.IGNORECASE)
        if m:
            try:
                results = research_topic(m.group(1))
                lines = [f"{i+1}. {r['title']}\n   {r['url']}"
                         for i, r in enumerate(results)]
                return ("Top results:\n" + "\n".join(lines)), "idle"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^read email (.+)$", msg, re.IGNORECASE)
        if m:
            try:
                mail = read_email_file(m.group(1))
                return (f"From: {mail['from']}\nTo: {mail['to']}\n"
                        f"Date: {mail['date']}\nSubject: {mail['subject']}\n\n"
                        f"{mail['body']}"), "idle"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^read calendar (.+)$", msg, re.IGNORECASE)
        if m:
            try:
                events = read_calendar_file(m.group(1))
                if not events:
                    return "No events found in that calendar file.", "idle"
                lines = [f"{e['start']}: {e['summary']}"
                         + (f" at {e['location']}" if e["location"] else "")
                         for e in events[:10]]
                return "Upcoming events:\n" + "\n".join(lines), "idle"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r'^git commit(?: in (.+?))? message "(.+)"$', msg, re.IGNORECASE)
        if m:
            try:
                return git_commit(m.group(1), m.group(2)), "celebrating"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^git branch(?: in (.+?))? (\S+)$", msg, re.IGNORECASE)
        if m:
            try:
                return git_branch(m.group(1), m.group(2)), "celebrating"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^run script (\S+)$", msg, re.IGNORECASE)
        if m:
            if self._strict():
                self.pending = ("run", resolve_path(m.group(1)))
                return (f"Strict mode: run {m.group(1)}? "
                        "Reply 'yes' to run it or 'no' to cancel."), "waiting"
            try:
                code, out, err = run_script(m.group(1))
                reply = f"Exit code {code}."
                if out:
                    reply += f"\nOutput:\n{out}"
                if err:
                    reply += f"\nErrors:\n{err}"
                return reply, "celebrating" if code == 0 else "error"
            except ToolError as e:
                return str(e), "error"

        m = re.match(r"^wifi (on|off)$", low)
        if m:
            try:
                return wifi_toggle(m.group(1) == "on"), "happy"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^brightness (\d+)$", low)
        if m:
            try:
                return set_brightness(int(m.group(1))), "happy"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^(sleep|shutdown|restart)( computer| pc)?$", low)
        if m:
            action = m.group(1)
            self.pending = ("power", action)
            return (f"Are you sure you want to {action} the computer? "
                    "Reply 'yes' to confirm or 'no' to cancel."), "waiting"

        m = re.match(r"^merge pdfs? (.+?) into (\S+)$", msg, re.IGNORECASE)
        if m:
            try:
                dest = pdf_merge(m.group(1).split(), m.group(2))
                log_work("merge pdf", dest)
                return f"Merged into {dest}.", "celebrating"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^split pdf (\S+) pages ([\d,\-]+) into (\S+)$",
                     msg, re.IGNORECASE)
        if m:
            try:
                dest = pdf_split(m.group(1), m.group(2), m.group(3))
                return f"Pages saved to {dest}.", "celebrating"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^convert image (\S+) to pdf (\S+)$", msg, re.IGNORECASE)
        if m:
            try:
                dest = image_to_pdf(m.group(1), m.group(2))
                return f"Saved {dest}.", "celebrating"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^read text from image (\S+)$", msg, re.IGNORECASE)
        if m:
            try:
                return ocr_image(m.group(1)), "idle"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^convert media (\S+) to (\S+)$", msg, re.IGNORECASE)
        if m:
            try:
                dest = media_convert(m.group(1), m.group(2))
                return f"Converted to {dest}.", "celebrating"
            except ToolError as e:
                return str(e), "sad"

        m = re.match(r"^remind me every (\d+) minutes? to (.+)$", low)
        if m:
            minutes = int(m.group(1))
            if self.on_reminder is None:
                return ("Reminders need the app window — open Buddy and ask "
                        "again."), "sad"
            self.reminders.remind_every(minutes * 60, m.group(2),
                                        self._reminder_fired)
            return (f"I'll remind you every {minutes} minutes to {m.group(2)} "
                    "while I'm running."), "happy"

        if low == "recent work":
            entries = load_work_log()
            if not entries:
                return "Nothing recorded yet — create or copy a file first.", "idle"
            lines = [f"{e['time']}: {e['action']} — {e['detail']}"
                     for e in entries[-10:]]
            return "Recent work:\n" + "\n".join(lines), "idle"

        m = re.match(r"^set ai backend to (ollama|lmstudio|custom|off)$", low)
        if m:
            self._save_setting("llm_backend", m.group(1))
            self.settings_changed["llm_backend"] = m.group(1)
            return f"AI backend set to {m.group(1)}.", "happy"

        m = re.match(r"^set ai model to (\S+)$", low)
        if m:
            self._save_setting("llm_model", m.group(1))
            self.settings_changed["llm_model"] = m.group(1)
            return f"AI model set to {m.group(1)}.", "happy"

        if low == "ai status":
            config = describe_backend(load_settings())
            if config is None:
                return ("No AI backend configured — Buddy runs fully offline "
                        "on its command brain. Set one in Settings to enable "
                        "'ask ai ...'."), "idle"
            return (f"AI backend: {config['backend']}\n"
                    f"Model: {config['model'] or '(not set)'}\n"
                    f"Server: {config['base']}"), "idle"

        m = re.match(r"^ask ai (.+)$", msg, re.IGNORECASE)
        if m:
            try:
                return ask_ai(m.group(1), load_settings()), "speaking"
            except ToolError as e:
                return str(e), "sad"

        # 15b. Pet compliments (checked late so commands always win).
        if re.search(r"\b(good boy|good girl|good pet|who'?s a good)\b", low):
            return "Woof! I mean... thank you! *happy wiggle*", "love"
        if re.search(r"(you'?re|you are|ur|so|such a)\s+(cute|adorable)"
                     r"|^cute\b", low):
            return "Aww, thank you! *blushes and wags tail*", "love"

        # 16. Fallback: honest, never faked.
        return ("Hmm, I don't know how to do that one yet. I'm a little offline pet, "
                "so I understand task commands best. Type 'help' to see everything "
                "I can do!"), "thinking"

    def _reminder_fired(self, message):
        # The UI replaces this hook with a popup. Headless default: print.
        print(f"[Buddy reminder] {message}")
