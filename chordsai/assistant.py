"""Turns one visitor message into one reply: text plus the chords and notes the page can play."""

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import timedelta

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from .agent import SearchFunction, build_graph, make_llm, make_tools, note_item
from .config import Settings
from .models import resolve_model
from .music import MusicError, parse_chord, parse_note
from .sessions import RateLimiter, Session, SessionStore

log = logging.getLogger(__name__)

RESET_WORDS = {"reset", "restart", "start over", "clear"}
MAX_ITEMS = 12


def welcome(search_enabled: bool) -> str:
    song = " or 'Chords of Let It Be'" if search_enabled else ""
    return (
        "Hi! I explain and play chords. Try 'Play C major 7', 'Play the notes of Am', "
        f"'What is a sus4 chord?'{song}. Press ▶ next to a chord to hear it, or click the piano keys below."
    )


class NotConfiguredError(RuntimeError):
    """The message needs the language model, but the server has no GROQ_API_KEY."""


@dataclass
class Reply:
    text: str
    play: list[dict] = field(default_factory=list)


# ------------------------------------------------------------------ no-LLM shortcuts

_QUICK = re.compile(
    r"^(?:please\s+)?(?:(?:play|show)\s+(?:me\s+)?)?(?:the\s+)?(?:notes?\s+(?:of|in)\s+(?:the\s+)?)?"
    r"(?P<kind>note\s+|chord\s+)?(?P<name>.+?)(?:\s+chord)?(?:\s+please)?\s*[.!?]*$",
    re.IGNORECASE,
)
_SPLIT = re.compile(r"\s*(?:,|\band\b|\bthen\b|\s)\s*", re.IGNORECASE)


def _chord_or_note(name: str, kind: str) -> dict:
    if kind == "note":
        return note_item(parse_note(name))
    try:
        return parse_chord(name).to_dict()
    except MusicError:
        return note_item(parse_note(name))


def quick_reply(message: str) -> Reply | None:
    """Answers messages that are just chord or note names ('Cmaj7', 'play Am and F', 'note A4')
    in plain Python: instant, exact and free. Anything else returns None and goes to the model."""
    match = _QUICK.match(message.strip())
    if not match:
        return None
    kind = (match["kind"] or "").strip().lower()
    name = match["name"].strip()
    try:
        items = [_chord_or_note(name, kind)]
    except MusicError:
        tokens = [token for token in _SPLIT.split(name) if token]
        if not 1 < len(tokens) <= 8:
            return None
        try:
            items = [_chord_or_note(token, kind) for token in tokens]
        except MusicError:
            return None
    if len(items) == 1:
        item = items[0]
        notes = " ".join(note["name"] for note in item["notes"])
        text = f"{item['name']} ({item['label']}): {notes}. Press ▶ to hear it."
        if item["type"] == "note":
            text = f"{item['label']}. Press ▶ to hear it."
    else:
        text = f"Here are {', '.join(item['name'] for item in items)}. Press ▶ on each one to hear it."
    return Reply(text=text, play=items)


_CHORDS_LINE = re.compile(r"^[\s\-•]*Chords?\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def chords_in_reply(text: str) -> list[dict]:
    """Chords listed on 'Chords: G D Em C' lines (the format the prompt asks for song results)."""
    items = []
    for line in _CHORDS_LINE.findall(text):
        for token in re.split(r"[\s,|→>]+", line):
            token = token.strip(".;:()[]").split("/")[0]  # slash chord → its main chord
            if not token:
                continue
            try:
                items.append(parse_chord(token).to_dict())
            except MusicError:
                continue
    return items


def _unique(items: list[dict]) -> list[dict]:
    seen, result = set(), []
    for item in items:
        key = (item["type"], item["name"])
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result[:MAX_ITEMS]


# ------------------------------------------------------------------------ assistant


class Assistant:
    def __init__(self, settings: Settings, llm: BaseChatModel | None = None, search: SearchFunction | None = None):
        """`llm` and `search` can be injected (tests use fakes); by default they come from Groq and Tavily."""
        self.settings = settings
        self.sessions = SessionStore(ttl=timedelta(minutes=settings.session_ttl_minutes))
        self.limiter = RateLimiter(settings.messages_per_session_per_hour, settings.messages_per_day)
        self._llm = llm
        self._tools = make_tools(settings, search)
        self._graph = None
        self._lock = threading.Lock()
        self.model: str | None = None

    @property
    def configured(self) -> bool:
        return self._llm is not None or bool(self.settings.groq_api_key)

    @property
    def search_enabled(self) -> bool:
        return any(t.name == "search_chords" for t in self._tools)

    def _get_graph(self):
        # Built lazily so the page (and the piano) work without an API key.
        with self._lock:
            if self._graph is None:
                llm = self._llm
                if llm is None:
                    self.model = resolve_model(self.settings.groq_api_key, self.settings.model)
                    llm = make_llm(self.settings, self.model)
                self._graph = build_graph(llm, self._tools)
            return self._graph

    def reply(self, session: Session, message: str) -> Reply:
        message = message.strip()
        if message.lower() in RESET_WORDS:
            session.reset()
            return Reply("Conversation cleared. " + welcome(self.search_enabled))
        quick = quick_reply(message)
        if quick:
            return quick
        if not self.configured:
            raise NotConfiguredError
        state = self._get_graph().invoke(
            {"messages": [HumanMessage(message)]},
            {"configurable": {"thread_id": session.thread_id}, "recursion_limit": 20},
        )
        return self._from_turn(state["messages"])

    @staticmethod
    def _from_turn(messages: list) -> Reply:
        last_user = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        turn = messages[last_user + 1 :]
        items = [m.artifact for m in turn if isinstance(m, ToolMessage) and isinstance(m.artifact, dict)]
        answer = next((m for m in reversed(turn) if isinstance(m, AIMessage)), None)
        text = str(answer.content).strip() if answer else ""
        items += chords_in_reply(text)
        return Reply(text=text or "Sorry, I have no answer for that. Could you rephrase it?", play=_unique(items))
