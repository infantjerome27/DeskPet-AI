# Buddy — your offline desktop pet AI

A small, cute desktop pet that lives on your Windows PC, chats with you, and
does real tasks — completely offline. No account, no internet needed, no data
leaves your computer.

## What Buddy can do

- **Chat** — say hello, ask how it is, hear a joke, or say "my name is ..."
  and it remembers you.
- **Open apps** — `open notepad`, `open calculator`, `open paint`, `open browser`
- **Files** — `list files in Documents`, `read myfile.txt`,
  `create file todo.txt with Buy milk`, `search files for birthday in Documents`
- **Organise** — `copy a.txt to b.txt`, `move a.txt to Documents`,
  `rename a.txt to b.txt`, `create folder Photos`, `recent files in Documents`,
  `file info report.docx`, `open file report.docx`
- **Delete safely** — `delete old.txt` always asks "Are you sure?" first.
- **Documents (real Word files!)** — `create document Report.docx title "My Report" heading "Intro" paragraph "Hello world" bullet "First point"`, then `add to document Report.docx paragraph "More"`, and `read document Report.docx` (works for txt, docx, csv, json)
- **Convert** — `convert notes.txt to docx` (Markdown headings and bullets
  become real Word headings and bullets)
- **Spreadsheets** — `create spreadsheet Data.csv headers "Name,Age" rows "Asha,20" "Ravi,21"`
- **Summarise** — `summarize file notes.txt` (lines, words, opening lines)
- **Notes** — `note: Call Amma at 6`, then `show notes`
- **Reminders** — `remind me in 10 minutes to drink water` (pops up on screen)
- **Maths** — `calculate 12 * 8 + 5`
- **Time, date, computer info** — `what time is it`, `system info`
- **Web** — `search the web for cute cats` opens your browser
  (this one feature needs internet, like any browser does)
- **Settings** — `set pet name to Max`, `set pet color to blue`,
  `set greeting to "Hey boss!"`, `set chat font size to 14`,
  `show settings`, `reset settings`
- **Apps** — `open word`, `open excel`, `open powerpoint`, `open outlook`,
  `open onenote`, `open vscode`, `open spotify`, `open whatsapp`,
  `open zoom`, `open vlc`, `open firefox` — any installed Windows app
  works by name. `open file Report.docx` opens a file in its default
  app (Word for Word files). `open word with Report.docx` opens a
  file inside a chosen app.
- **Microsoft 365 & Copilot** — `open copilot`, `open office 365`,
  `open onedrive`, `open teams` open those services in your browser,
  signed in as you. `ask copilot what is a pivot table` opens Copilot
  and copies your question to the clipboard — paste it there.
  If OneDrive syncs to your PC, Buddy works on those files like any
  folder: `list files in onedrive`, `read onedrive/notes.txt`.

Click Buddy to open the chat. Right-click Buddy for a menu. Drag Buddy
anywhere on your screen — it stays on top.

## How to run it (Windows)

1. Install Python 3.10 or newer from https://www.python.org/downloads/
   (during install, tick **"Add python.exe to PATH"**).
2. Unzip this folder anywhere you like.
3. Double-click **start.bat**. Buddy appears on your desktop.

That's it — no other installs, no sign-in, nothing to configure.

## How to use Buddy

- **Click the pet** — the chat box opens right beside it. Type an
  instruction in plain words (`create document Report.docx title "My Report"`,
  `open excel`, `list files in Documents`) and Buddy does it.
- **Talk to it** — click the 🎤 mic button and speak; click 🔊/🔇 to
  turn its spoken replies on or off. Voice uses Windows speech
  recognition and speech synthesis (Windows only, no downloads).
- **Move it** — drag the pet anywhere. Double-click for a trick.
  Right-click for a menu (chat, trick, settings, screenshot, quit).
- **Change the pet** — right-click → Settings, or type `be a cat`,
  `be a puppy`, `be a robot`, `be a spirit`. In Settings you can also
  change its name, colour, size (120–280), move speed, greeting, chat
  text size, voice volume, confirmation mode, and AI backend.
- **On its own** — when "Wander & play" is on, Buddy glides around the
  desktop, hides and peeks back, plays tricks, and hangs out near your
  cursor. After a minute with no keyboard activity it falls asleep
  (any click or keypress wakes it). Say `autonomy off` to make it stay put.
- **Start with Windows** — type `start with windows` (and
  `stop starting with windows` to undo).
- **Safe by default** — deletes and bulk renames always ask first, and
  show an approval popup near the pet: Approve or Deny. Turn on
  **Strict** confirmation mode (Settings, or `confirmation mode strict`)
  and Buddy also asks before running scripts, overwriting files, and
  power actions like sleep/shutdown.
- **Ask the AI (optional)** — Buddy's built-in brain handles every task
  command offline. For open-ended questions, point it at a local model:
  install Ollama (https://ollama.com), run `ollama pull llama3`, then in
  Settings set AI backend to Ollama and model to `llama3`. Then
  `ask ai ...` works. LM Studio and OpenAI-compatible APIs work the same
  way; a custom API key is stored only in Buddy's settings file on your
  own PC, never sent anywhere except the server you configured.

## What Buddy shows while it works (agent states)

- **Thinking** — contemplative look + "..." thought bubble while your
  prompt is processed.
- **Working** — typing paws on a mini keyboard while tools run.
- **Busy** — focused, narrowed eyes while a script or test runs.
- **Waiting for approval** — worried look, sweat drop and "?" while a
  confirmation popup waits for you.
- **Celebration** — jumping, dancing, sparkles and a chime when a task
  finishes (documents, spreadsheets, presentations, downloads, commits).
- **Error** — worried look + red alarm triangle when something fails.
- **Sleeping** — closed eyes + floating Z's after a minute idle.

## Realistic photo pets (like DeskPet)

Buddy now also comes with photorealistic pets, not just drawings:
a real orange tabby cat, a real border collie dog, and a real grey
kitty — transparent photos that sit on your desktop like the pets in
the DeskPet screenshot, and still glide, jump, hide and play like any
other Buddy pet. Switch with `be a real cat`, `be a real dog`,
`be a real kitty`, or Settings → Pet → Real Cat / Real Dog / Real
Kitty. The orange cat is the default pet on a fresh install. Each
photo pet also has an animated GIF version (`real_cat.gif` etc.) that
loops gentle idle motion — breathing, blinking, tail swishes — so the
pet feels alive on your desktop instead of frozen. If a GIF is
missing, the still photo shows; if both are missing, the matching
drawn pet shows.

The photos live in the `pets/` folder (`real_cat.png`, `real_dog.png`,
`real_kitty.png`). You can replace any of them with your own pet's
transparent PNG of the same style (animal facing the camera, full
body) and Buddy will show yours instead. If a photo file is missing,
Buddy falls back to the matching drawn pet so nothing breaks.

## More things Buddy can do (v4–v5)

- **Pets** — Blob, Cat, Puppy, Robot, Spirit. Eyes track your mouse and
  the head tilts toward it; tails wag, ears twitch, paws step while
  walking. The pet window is transparent on Windows — only the pet
  itself floats on your desktop.
- **Web** — `download https://... to Downloads` (files land in
  Images/Documents/Audio/Video/Archives subfolders), `scrape <url>`,
  `research <topic>` (top results with links).
- **Mail & calendar files** — `read email saved.eml`, `read calendar
  holidays.ics` (exported mail/calendar files; reading your live
  mailbox or calendar needs your Microsoft/Google sign-in, which Buddy
  never asks for — it works on files you export instead).
- **Code & Git** — `run python x.py`, `run script x.ps1`,
  `git commit in folder message "msg"`, `git branch in folder name`,
  `git status`, `git log`.
- **OS control (Windows)** — `wifi on`, `wifi off`, `brightness 70`,
  `sleep computer` / `shutdown computer` / `restart computer`
  (power actions always ask first).
- **Memory** — `recent work` lists what Buddy has made for you;
  `note: ...`, `remember that ...`, and `what do you remember` persist
  notes and facts on your PC.
- **Recurring reminders** — `remind me every 30 minutes to drink water`.
- **Optional extras (install once if you want them)** — PDF merge/split
  (`merge pdfs a.pdf b.pdf into out.pdf`, `split pdf a.pdf pages 1,3
  into out.pdf`) need `pip install pypdf`; image→PDF and OCR
  (`convert image photo.png to pdf photo.pdf`,
  `read text from image photo.png`) need `pip install pillow`
  (and Tesseract for OCR); media conversion
  (`convert media song.wav to song.mp3`) needs the FFmpeg program.
  Without them Buddy tells you exactly what's missing instead of
  pretending.

## Make a standalone Buddy.exe (Windows)

1. Install Python 3.10+ with "Add python.exe to PATH" ticked.
2. Double-click **build_exe.bat** (it installs PyInstaller once, then
   builds). Your app appears as `dist\Buddy.exe` — copy it anywhere and
   double-click it; no Python needed on that PC afterwards.
3. Note: the .exe must be built on Windows. It cannot be built from
   Linux or a Mac.

## Honest limits

- Buddy is a local command brain, not a cloud LLM: it prepares documents
  and runs tasks from your own words; it does not invent content. For
  open-ended chat, connect Ollama/LM Studio as above.
- No live mailbox, calendar, Teams/Slack/WhatsApp access, and no
  Microsoft 365 sign-in: those need your own account connection and app
  registration, and Buddy never asks for your Microsoft password. It
  opens the 365/Copilot web apps in your browser, signed in as you.
- No installs/uninstalls, volume/Wi-Fi/Bluetooth toggles beyond the
  commands above, RPA mouse macros, or MySQL/PostgreSQL: those need
  extra Windows tooling (pywin32, pyautogui, database drivers) that
  Buddy deliberately does not bundle. The commands it does offer are
  the ones verified by its test suite.

## How to run the tests

Double-click **run_tests.bat**, or run:

```
python -m unittest discover -s tests -v
```

## Honest limits (please read)

- Buddy understands **task commands** (the list above) with a local,
  built-in brain. It is fast and private, but it is **not** a cloud AI
  like Muse — it cannot answer open-ended knowledge questions, invent
  content from nothing, or reason like a large model. It prepares
  documents from the words you give it, and when it doesn't understand
  something, it says so and suggests `help` instead of guessing.
- **Microsoft 365, honestly:** Buddy opens your Office desktop apps and
  creates real Word/Excel/PowerPoint files that open natively in
  Office 365, and it opens Copilot/Teams/OneDrive in your browser
  signed in as you. What it does **not** do: sign into your Microsoft
  account itself, read your Outlook mailbox, or reach OneDrive/SharePoint
  in the cloud — that needs a Microsoft sign-in and app registration
  that only you can approve on your PC, and Buddy never asks for your
  Microsoft password. If OneDrive syncs to your PC, local synced files
  work fully. Buddy also never stores passwords — use a real password
  manager for those.
- Web search only opens your browser — results need an internet connection.
- File commands work inside your own files. Delete always asks first,
  and Buddy never deletes whole folders.
- Buddy runs on Windows with Python. It is a Python program, not a
  single .exe file — `start.bat` is the launcher.

## Files

- `main.py` — starts Buddy
- `ui.py` — pet window + chat window
- `pet.py` — the animated pet (moods, blinking, bouncing, reactions)
- `brain.py` — understands your prompts
- `tools.py` — files, apps, notes, reminders, calculator, system info
- `docs.py` — the Word document engine (create, read, append, convert)
- `office.py` — the Excel/PowerPoint engines and the PDF reader
- `tests/` — unit tests for the brain, tools and pet animation
