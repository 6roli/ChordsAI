from dataclasses import replace

from langchain_core.messages import ToolMessage

from chordsai.agent import make_search_tool, make_tools, play_chord, play_note, system_prompt


def call(tool, **args) -> ToolMessage:
    return tool.invoke({"name": tool.name, "args": args, "id": "call_1", "type": "tool_call"})


def test_play_chord_returns_notes_for_the_browser_not_sound():
    message = call(play_chord, name="Cmaj7")
    assert "C4 E4 G4 B4" in message.content
    assert message.artifact["name"] == "Cmaj7"
    assert [n["midi"] for n in message.artifact["notes"]] == [60, 64, 67, 71]


def test_play_chord_with_a_plain_name_plays_the_whole_chord():
    assert [n["name"] for n in call(play_chord, name="C").artifact["notes"]] == ["C4", "E4", "G4"]


def test_play_note():
    message = call(play_note, name="A")
    assert message.artifact == {
        "type": "note",
        "name": "A4",
        "label": "A4 (440 Hz)",
        "notes": [{"name": "A4", "midi": 69, "frequency": 440.0}],
    }


def test_unknown_names_explain_the_problem_to_the_model():
    message = call(play_chord, name="Hmaj")
    assert message.artifact is None and "note name" in message.content
    assert call(play_note, name="Q").artifact is None


def test_search_tool_only_offered_with_a_tavily_key(settings):
    assert [t.name for t in make_tools(settings)] == ["play_chord", "play_note"]
    assert [t.name for t in make_tools(settings, search=lambda q: [])][-1] == "search_chords"
    # With a key the real Tavily tool is created (no request is made until it is used).
    assert make_tools(replace(settings, tavily_api_key="tvly-test"))[-1].name == "search_chords"


def test_search_tool_passes_sources_and_warns_against_lyrics():
    queries = []

    def fake_search(query):
        queries.append(query)
        return [{"title": "Let It Be chords", "url": "https://example.com/let-it-be", "content": "C G Am F " * 400}]

    output = make_search_tool(fake_search).invoke({"song": "Let It Be"})
    assert queries == ["Let It Be chords"]
    assert "https://example.com/let-it-be" in output and "Never repeat lyrics" in output
    assert len(output) < 2000  # long pages are cut


def test_search_tool_handles_no_results_and_failures():
    assert "No results" in make_search_tool(lambda q: []).invoke({"song": "x"})

    def broken(query):
        raise ConnectionError("down")

    assert "unavailable" in make_search_tool(broken).invoke({"song": "x"})


def test_prompt_depends_on_search_availability():
    assert "NEVER include lyrics" in system_prompt(search_enabled=True)
    assert "Song search is disabled" in system_prompt(search_enabled=False)
