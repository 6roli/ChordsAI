import pytest
from langchain_core.messages import AIMessage

from chordsai import web
from chordsai.assistant import Assistant, Reply

from conftest import FakeLLM, tool_call


@pytest.fixture
def client(monkeypatch, settings):
    # A fresh assistant per test, with a scripted model instead of Groq.
    llm = FakeLLM(responses=[tool_call("play_chord", name="G7"), AIMessage("G7 is a dominant seventh chord.")])
    monkeypatch.setattr(web, "assistant", Assistant(settings, llm=llm))
    web.app.config["TESTING"] = True
    return web.app.test_client()


def test_home_page_has_chat_piano_and_no_inline_script(client):
    page = client.get("/").get_data(as_text=True)
    assert "Play C major 7" in page and "← Portfolio" in page
    assert page.count('class="key ') == 25 and 'data-frequency="440.0"' in page
    assert "<script>" not in page and 'src="/static/chat.js"' in page
    assert "Chords of Let It Be" not in page  # song search is off without a Tavily key


def test_static_files_are_served(client):
    assert b"AudioContext" in client.get("/static/chat.js").data
    assert client.get("/static/chat.css").status_code == 200


def test_chat_returns_reply_and_chords_to_play(client):
    data = client.post("/chat", json={"message": "What is a G7?"}).get_json()
    assert data["reply"] == "G7 is a dominant seventh chord."
    assert data["play"][0]["name"] == "G7"
    assert [n["name"] for n in data["play"][0]["notes"]] == ["G4", "B4", "D5", "F5"]


def test_chord_names_work_without_the_model(client, monkeypatch, settings):
    monkeypatch.setattr(web, "assistant", Assistant(settings))  # no key at all
    data = client.post("/chat", json={"message": "Am F C G"}).get_json()
    assert [item["name"] for item in data["play"]] == ["Am", "F", "C", "G"]
    response = client.post("/chat", json={"message": "Why is minor sad?"})
    assert response.status_code == 503 and "piano" in response.get_json()["error"]


def test_chat_keeps_the_visitor_session(client, monkeypatch):
    monkeypatch.setattr(web.assistant, "reply", lambda session, message: Reply(session.id))
    first = client.post("/chat", json={"message": "hi"}).get_json()["reply"]
    second = client.post("/chat", json={"message": "again"}).get_json()["reply"]
    assert first == second
    assert web.app.test_client().post("/chat", json={"message": "hi"}).get_json()["reply"] != first


def test_chat_rejects_bad_input(client):
    assert client.post("/chat", json={}).status_code == 400
    assert client.post("/chat", json={"message": "   "}).status_code == 400
    assert client.post("/chat", json={"message": 42}).status_code == 400
    assert client.post("/chat", json={"message": "x" * 5000}).status_code == 400


def test_rate_limit_answers_429(client, monkeypatch):
    monkeypatch.setattr(web.assistant.limiter, "check", lambda session, now: "limit reached")
    response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 429 and response.get_json()["error"] == "limit reached"


@pytest.mark.parametrize(
    ("error_name", "status", "expected"),
    [
        ("RateLimitError", 503, "quota"),
        ("NotFoundError", 503, "no longer available"),
        ("AuthenticationError", 503, "key was rejected"),
        ("APITimeoutError", 503, "did not answer"),
        ("ZeroDivisionError", 500, "went wrong"),
    ],
)
def test_model_errors_become_friendly_messages(client, monkeypatch, error_name, status, expected):
    error_class = type(error_name, (Exception,), {})

    def fail(session, message):
        raise error_class("boom")

    monkeypatch.setattr(web.assistant, "reply", fail)
    response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == status and expected in response.get_json()["error"]


def test_security_headers_and_health(client):
    response = client.get("/health")
    assert response.get_json() == {
        "status": "ok",
        "configured": True,
        "search_enabled": False,
        "active_sessions": 0,
        "model": None,
    }
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp and "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert response.headers["X-Content-Type-Options"] == "nosniff"
