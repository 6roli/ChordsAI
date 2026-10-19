from datetime import datetime, timedelta

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from chordsai.agent import recent
from chordsai.assistant import Assistant, NotConfiguredError, chords_in_reply, quick_reply, welcome
from chordsai.sessions import SessionStore

from conftest import FakeLLM, tool_call


def visitor():
    return SessionStore(ttl=timedelta(hours=1)).get_or_create(None, datetime(2026, 10, 19, 12))


def played(reply) -> list[str]:
    return [item["name"] for item in reply.play]


# ----------------------------------------------------------- answers without the model


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Cmaj7", ["Cmaj7"]),
        ("Play C major 7", ["Cmaj7"]),
        ("play the notes of Am", ["Am"]),
        ("Play the D minor chord please.", ["Dm"]),
        ("show me F#m", ["F#m"]),
        ("Am F C G", ["Am", "F", "C", "G"]),
        ("play G, D, Em and C", ["G", "D", "Em", "C"]),
        ("note A4", ["A4"]),
        ("play note C", ["C4"]),
        ("C4", ["C4"]),  # not a chord symbol, so a single note
        ("a minor", ["Am"]),
    ],
)
def test_quick_replies_need_no_model(message, expected):
    reply = quick_reply(message)
    assert reply is not None and played(reply) == expected


def test_quick_reply_text_lists_the_notes():
    assert "C4 E4 G4 B4" in quick_reply("Cmaj7").text
    assert "440 Hz" in quick_reply("note A").text


@pytest.mark.parametrize(
    "message",
    ["What is a sus4 chord?", "Chords of Let It Be", "hello", "Am I right", "Be nice", "play something happy"],
)
def test_questions_go_to_the_model(message):
    assert quick_reply(message) is None


def test_chords_line_in_song_answers_becomes_play_buttons():
    text = "Let It Be (suggested chords, may be inaccurate)\nChords: C G Am F, G/B x2.\nSource: https://example.com"
    assert [item["name"] for item in chords_in_reply(text)] == ["C", "G", "Am", "F", "G"]
    assert chords_in_reply("The A chord is happy.") == []  # only 'Chords:' lines count


# --------------------------------------------------------------- conversation with model


def test_model_turn_returns_text_and_the_chords_its_tools_looked_up(settings):
    llm = FakeLLM(
        responses=[
            tool_call("play_chord", name="Dm7"),
            AIMessage("Dm7 is a minor seventh chord: D F A C. Press play to hear it."),
        ]
    )
    reply = Assistant(settings, llm=llm).reply(visitor(), "What does a minor seventh on D sound like?")
    assert reply.text.startswith("Dm7 is a minor seventh")
    assert played(reply) == ["Dm7"]
    assert reply.play[0]["notes"][0]["frequency"] == 293.66
    # The second model call saw the tool result computed by music.py.
    assert isinstance(llm.received[1][-1], ToolMessage) and "D4 F4 A4 C5" in llm.received[1][-1].content


def test_song_search_flow_without_network(settings):
    llm = FakeLLM(
        responses=[
            tool_call("search_chords", song="Let It Be"),
            AIMessage("Suggested chords (may be inaccurate):\nChords: C G Am F\nSource: https://example.com/lib"),
        ]
    )
    search = lambda query: [{"title": "t", "url": "https://example.com/lib", "content": "C G Am F"}]  # noqa: E731
    assistant = Assistant(settings, llm=llm, search=search)
    assert assistant.search_enabled
    reply = assistant.reply(visitor(), "Chords of Let It Be")
    assert played(reply) == ["C", "G", "Am", "F"] and "example.com" in reply.text


def test_without_search_the_model_is_told_it_cannot_look_up_songs(settings):
    llm = FakeLLM(responses=[AIMessage("Song search is not available in this demo.")])
    assistant = Assistant(settings, llm=llm)
    assert not assistant.search_enabled
    assistant.reply(visitor(), "Chords of Let It Be")
    assert "Song search is disabled" in llm.received[0][0].content


def test_each_visitor_has_its_own_memory_and_reset_clears_it(settings):
    llm = FakeLLM(responses=[AIMessage("one"), AIMessage("two"), AIMessage("three"), AIMessage("four")])
    assistant = Assistant(settings, llm=llm)
    alice, bob = visitor(), visitor()
    assistant.reply(alice, "Tell me about chords")
    assistant.reply(alice, "And sevenths?")
    assert [m.content for m in llm.received[1] if isinstance(m, HumanMessage)] == ["Tell me about chords", "And sevenths?"]
    assistant.reply(bob, "Hi there")
    assert [m.content for m in llm.received[2] if isinstance(m, HumanMessage)] == ["Hi there"]
    assert "cleared" in assistant.reply(alice, "reset").text
    assistant.reply(alice, "New topic")
    assert [m.content for m in llm.received[3] if isinstance(m, HumanMessage)] == ["New topic"]


def test_without_groq_key_quick_replies_still_work(settings):
    assistant = Assistant(settings)
    assert not assistant.configured
    assert played(assistant.reply(visitor(), "Am")) == ["Am"]
    with pytest.raises(NotConfiguredError):
        assistant.reply(visitor(), "What is a chord?")


def test_history_window_never_starts_with_a_tool_result():
    messages = [HumanMessage("a"), tool_call("play_chord"), ToolMessage("x", tool_call_id="call_1"), AIMessage("b")]
    messages += [HumanMessage("c"), AIMessage("d")]
    assert recent(messages, limit=4) == messages[-2:]
    assert recent(messages, limit=50) == messages


def test_greeting_only_mentions_songs_when_search_is_enabled():
    assert "Let It Be" in welcome(True) and "Let It Be" not in welcome(False)
    assert "Play C major 7" in welcome(False)
