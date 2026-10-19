"""The tools and the single LangGraph agent.

       agent (LLM) ──tool calls──▶ tools ──▶ agent … ──▶ reply

The tools never make sound: the server has no speakers. They RETURN the notes (name,
MIDI number, frequency) as a LangChain "artifact"; the web page plays them in the
visitor's browser. Chord notes always come from music.py, never from the model.
"""

import logging
from collections.abc import Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from .config import Settings
from .models import model_options
from .music import MusicError, Note, parse_chord, parse_note

log = logging.getLogger(__name__)

# A search function takes a query and returns results like Tavily's: [{"title", "url", "content"}, ...].
SearchFunction = Callable[[str], list[dict]]

MAX_HISTORY = 16


def note_item(note: Note) -> dict:
    return {"type": "note", "name": note.name, "label": f"{note.name} ({note.frequency:g} Hz)", "notes": [note.to_dict()]}


@tool(response_format="content_and_artifact")
def play_chord(name: str) -> tuple[str, dict | None]:
    """Look up the notes of a chord so the visitor's browser can play it.

    `name` is one chord symbol such as C, Am, F#m, Bb7, Cmaj7, Dm7, Gsus4, Bdim, Eaug, Cadd9 or Am7b5.
    """
    try:
        chord = parse_chord(name)
    except MusicError as error:
        return str(error), None
    notes = " ".join(note.name for note in chord.notes)
    return f"{chord.name} ({chord.label}): {notes}. The page shows a play button for it.", chord.to_dict()


@tool(response_format="content_and_artifact")
def play_note(name: str) -> tuple[str, dict | None]:
    """Look up a single note so the visitor's browser can play it. `name` is e.g. C, F#, Bb3 or A4 (octave 4 by default)."""
    try:
        note = parse_note(name)
    except MusicError as error:
        return str(error), None
    return f"{note.name}: MIDI {note.midi}, {note.frequency:g} Hz. The page shows a play button for it.", note_item(note)


def make_search_tool(search: SearchFunction) -> BaseTool:
    @tool
    def search_chords(song: str) -> str:
        """Search the web for the chords of a song. `song` is the title and, if known, the artist."""
        try:
            results = search(f"{song} chords")
        except Exception as error:  # noqa: BLE001 — the visitor gets an explanation, not a crash
            log.warning("Chord search failed: %s", type(error).__name__)
            return "The web search is unavailable right now. Tell the user to try again later."
        if not results:
            return "No results were found for that song."
        parts = [
            f"Source: {result.get('title', '')} {result.get('url', '')}\n{(result.get('content') or '')[:1500]}"
            for result in results[:3]
        ]
        return (
            "Web results. Use them ONLY to identify the chord names and the source link. "
            "Never repeat lyrics.\n\n" + "\n\n".join(parts)
        )

    return search_chords


def tavily_search(api_key: str) -> SearchFunction:
    from langchain_tavily import TavilySearch

    client = TavilySearch(max_results=3, tavily_api_key=api_key)

    def search(query: str) -> list[dict]:
        result = client.invoke({"query": query})
        return result.get("results", []) if isinstance(result, dict) else []

    return search


def make_tools(settings: Settings, search: SearchFunction | None = None) -> list[BaseTool]:
    """Chord and note tools always; song search only when a TAVILY_API_KEY (or a test search) is given."""
    if search is None and settings.tavily_api_key:
        search = tavily_search(settings.tavily_api_key)
    tools: list[BaseTool] = [play_chord, play_note]
    if search is not None:
        tools.append(make_search_tool(search))
    return tools


SYSTEM_PROMPT = """You are ChordsAI, a friendly music assistant in a portfolio demo. You explain chords and notes
and let the visitor hear them in their browser.
- When the user names chords or notes, call play_chord (one call per chord, at most 8) or play_note.
  Never work out chord notes yourself: use the tool result. The page adds a play button for every
  chord or note you looked up; never claim that you produced sound yourself.
- You can explain chord theory briefly (intervals, why a chord sounds happy or sad, common progressions).
- Keep answers short. Write plain text without Markdown (no asterisks or # headings); use '- ' for lists.
{search_rules}"""

SEARCH_RULES = """- For the chords of a song, call search_chords once. Then reply with the song name, one line that
  starts exactly with 'Chords:' followed by the distinct chord symbols separated by spaces
  (for example 'Chords: G D Em C'), the progression if it is clear, and the source link.
  Say these are suggested chords found on the web and may be inaccurate.
  NEVER include lyrics, not even one line. You do not need to call play_chord for these chords:
  the page adds play buttons for the 'Chords:' line."""

NO_SEARCH_RULES = """- Song search is disabled in this demo, so you cannot look up the chords of songs and must not guess them.
  If asked, say so politely and offer to play chords the user names (for example 'Play G D Em C')."""


def system_prompt(search_enabled: bool) -> str:
    return SYSTEM_PROMPT.format(search_rules=SEARCH_RULES if search_enabled else NO_SEARCH_RULES)


def recent(messages: list[AnyMessage], limit: int = MAX_HISTORY) -> list[AnyMessage]:
    """The last messages, starting at a user message so no tool result is left without its call."""
    window = messages[-limit:]
    for index, message in enumerate(window):
        if isinstance(message, HumanMessage):
            return window[index:]
    return messages[-1:]


def make_llm(settings: Settings, model: str) -> BaseChatModel:
    from langchain_groq import ChatGroq

    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    # One retry only: on a rate limit we prefer telling the visitor quickly.
    return ChatGroq(
        model=model, temperature=0, api_key=settings.groq_api_key, max_retries=1, timeout=45, **model_options(model)
    )


def build_graph(llm: BaseChatModel, tools: list[BaseTool]):
    """One agent with tools. `llm` is any LangChain chat model with tool calling (a fake one in tests)."""
    model = llm.bind_tools(tools)
    system = SystemMessage(system_prompt(any(t.name == "search_chords" for t in tools)))

    def agent(state: MessagesState) -> dict:
        return {"messages": [model.invoke([system, *recent(state["messages"])])]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    # In-memory checkpoints: conversation history per visitor thread, lost on restart (fine for a demo).
    return graph.compile(checkpointer=InMemorySaver())
