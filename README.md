# ChordsAI

A small chat assistant that **explains chords and plays them in your browser**. Ask "Play C major 7", "Play the
notes of Am" or "What is a sus4 chord?" and press ▶ to hear the answer. There is also a two-octave on-screen piano.
Optionally, with a Tavily key, it can look up the chords of a song on the web.

Built with **LangGraph** and language models served by **Groq**. Sound comes from the **Web Audio API**.

| | |
|---|---|
| Live demo | *published on Render, URL added after the first deployment* |
| Portfolio page | https://portfolio.gabriel-olius.workers.dev/projects/chordsai/ |
| Original version | tag [`v0-original`](https://github.com/6roli/ChordsAI/tree/v0-original) (kept unchanged) |
| Cost | €0 (Render Free + Groq free tier, optional Tavily free credits, no payment methods) |

> **Demo notice:** messages are sent to Groq to generate answers; this app does not store them. Song chords found on
> the web are suggestions and may be inaccurate. The bot gives chord names and the source link only, never lyrics.

## How it works

```
Visitor message
   │
   ├─ just chord or note names?  ("Cmaj7", "play Am F C G", "note A4")
   │      └─ music.py (plain Python) → instant answer, no model, works without any key
   │
   └─ anything else ── LangGraph agent (LLM on Groq, memory per visitor)
          ├─ play_chord(name)    → notes from music.py (name, MIDI number, frequency)
          ├─ play_note(name)     → one note from music.py
          └─ search_chords(song) → Tavily web search (only if TAVILY_API_KEY is set)

Reply to the browser:  { "reply": "text", "play": [ {chord or note with its notes}, ... ] }
Browser: a ▶ button per chord; Web Audio plays one oscillator per note (chord or arpeggio)
```

The model never works out chord notes itself: the tools return them from `music.py`, which is fully tested. The
server never makes sound (a web server has no speakers); it returns the notes and the visitor's browser plays them.

### Original vs now

| Original (`v0-original`) | Now |
|---|---|
| Model `qwen-qwq-32b` (retired by Groq) | Model chosen from those the Groq account offers (preference list in `models.py`, currently `openai/gpt-oss-120b`); `GROQ_MODEL` can force one |
| `get_frequency` used `note - 10`: every note one semitone flat (A4 ≈ 415 Hz) | Equal temperament from MIDI numbers, A4 = 440 Hz, tested |
| Plain chord names like "C" played only the root note | "C" is a full C major chord; 20 chord qualities and common spellings ("C major 7", "Am7", "Bø", "F#m") |
| `play_chord` threads captured the loop variable (`lambda` bug) and played the same note | No threads on the server; the browser schedules all notes together |
| Audio played with `sounddevice` on the machine running Python (useless on a server) | Tools return note data; the page plays it with the Web Audio API |
| Supervisor bound agent *classes* as tools (could not work) | One agent with real tools |
| `playAgent` never printed replies (`messages is type(AIMessage)`) | Web chat page with replies and ▶ buttons |
| Duplicated `main()` blocks and imports in every script | One package `chordsai/` with a Flask app |
| 148-package UTF-16 `requirements.txt` with Windows-only packages (`pywin32`, `pywinpty`) | 7 pinned direct dependencies in `pyproject.toml` |
| Song search always on, could print lyrics | Optional; answers give chord names and the source link only, labelled as suggestions |
| No limits, no tests | Per-visitor (30/hour) and global (300/day) limits; 155 pytest tests, no key or network needed |

## Project layout

```
chordsai/
  music.py        Note and chord names → notes, MIDI numbers, frequencies (pure Python, no model)
  agent.py        Tools (play_chord, play_note, search_chords) and the LangGraph agent
  assistant.py    One message in → reply text + notes to play; no-model shortcut for chord names
  models.py       Picks a Groq model the account can use (Groq retires models regularly)
  config.py       Settings from environment variables (.env locally, secrets on Render)
  sessions.py     Per-visitor sessions and usage limits
  web.py          Flask app: page, /chat API, /health, security headers
  templates/, static/   Chat page and piano (plain HTML, CSS, JavaScript with Web Audio)
tests/            pytest tests with a fake model and fake search (no API key, no network)
render.yaml       Render deployment settings
pyproject.toml    Dependencies and project metadata
.env.example      Template for local secrets
```

## Technologies: what, where, why

| Technology | Runs where | Why |
|---|---|---|
| **Python 3.13** | Your computer and Render | Language of the server |
| **LangGraph** | Server | The agent loop (model → tools → model) and memory per conversation |
| **LangChain + langchain-groq** | Server | Common interface to the model and tool calling |
| **Groq** | Groq's cloud | Runs open models (currently OpenAI's open-weight gpt-oss) very fast; free tier with daily limits |
| **Tavily** (optional) | Tavily's cloud | Web search for song chords |
| **Flask + gunicorn** | Server | Web page and JSON API; gunicorn is the production web server |
| **Web Audio API** | Visitor's browser | Generates the sound: no audio files, no plugins |
| **pytest** | Your computer and Render's build | Automatic tests |
| **Render** | Render's cloud | Hosts the server for free and redeploys on every push to `main` |

## Run locally (VS Code)

Requirements: Python 3.12+ and Git.

```bash
git clone https://github.com/6roli/ChordsAI.git
cd ChordsAI
python -m venv .venv
.venv\Scripts\activate              # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -e ".[dev]"
copy .env.example .env              # macOS/Linux: cp .env.example .env
#   then put your own GROQ_API_KEY in .env  (free at https://console.groq.com/keys)
#   optional: TAVILY_API_KEY for song search (free at https://app.tavily.com)
flask --app chordsai.web run        # http://127.0.0.1:5000
```

Without any key the page still works: the piano plays, and typing chord names such as `Cmaj7` or `Am F C G` is
answered without the model. Questions ("why does minor sound sad?") need `GROQ_API_KEY`.

| Command | Purpose |
|---|---|
| `flask --app chordsai.web run --debug` | Development server with auto-reload |
| `python -m pytest` | Tests (no API key or network needed) |

## Publish on Render (free)

1. Merge `feature/web-demo` into `main` (Render deploys `main`).
2. Sign in at https://render.com with GitHub (no card needed for the free instance).
3. **New → Blueprint** → choose the `ChordsAI` repository. Render reads `render.yaml`.
4. When asked, paste your `GROQ_API_KEY`. `TAVILY_API_KEY` is optional: leave it empty to keep song search off.
   Both are stored as secrets. `FLASK_SECRET_KEY` is generated by Render.
5. Deploy. The build installs the dependencies and runs the tests. The address looks like `https://chordsai.onrender.com`.
6. Open `/health` to check: `"configured": true` and, if you added Tavily, `"search_enabled": true`.

After that, every push to `main` runs the tests and redeploys; if a test fails, the previous version stays online.

Free-plan behaviour: the service sleeps after 15 minutes without visitors and the next visit takes about a minute
to wake it. Render gives 750 free instance hours per month; without a payment method it suspends the service
instead of charging.

## Costs, limits and licences

| Item | Plan | Cost | Protection |
|---|---|---|---|
| Hosting | Render Free | €0 | No payment method → suspended, never billed |
| Language model | Groq free tier | €0 | Daily token limits per model; the app answers politely when they are reached. Don't add a card to Groq unless you decide to pay |
| Song search | Tavily free credits (optional) | €0 | Only used for song questions; off when no key is set |
| Abuse | — | — | 30 messages per visitor per hour, 300 per day in total, 300 characters per message |

Adjust the limits with environment variables (see `.env.example`).

- Dependencies are open source: Flask and python-dotenv (BSD-3-Clause), gunicorn, LangGraph, LangChain,
  langchain-groq and langchain-tavily (MIT). The browser sound uses only the built-in Web Audio API.
- Chord progressions found on the web belong to their sources: the bot shows the chord names with a link to the
  source and never reproduces lyrics.
- This repository has no licence file yet, so all rights are reserved by the author unless one is added.

## Security

- Never commit `.env` or keys. If a key is ever exposed, revoke it in the provider's dashboard and create a new one.
- Model replies are displayed as plain text, never as HTML.
- The page sends a Content-Security-Policy (scripts only from this site, no inline scripts) and cannot be embedded
  in other sites.
