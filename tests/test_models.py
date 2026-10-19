import pytest

from chordsai.models import PREFERENCES, choose, model_options


def test_picks_first_preferred_model_the_account_has():
    assert choose(None, PREFERENCES, {"openai/gpt-oss-20b", "some/other-model"}) == "openai/gpt-oss-20b"


def test_override_wins():
    assert choose("my/model", PREFERENCES, {"openai/gpt-oss-120b"}) == "my/model"


def test_without_model_list_trusts_preferences():
    assert choose(None, PREFERENCES, None) == PREFERENCES[0]


def test_clear_error_when_nothing_matches():
    with pytest.raises(RuntimeError, match="GROQ_MODEL"):
        choose(None, PREFERENCES, {"retired/model"})


def test_retired_prototype_model_is_never_preferred():
    assert "qwen-qwq-32b" not in PREFERENCES


def test_reasoning_models_answer_without_visible_reasoning():
    assert model_options("openai/gpt-oss-120b") == {"reasoning_effort": "low"}
    assert model_options("qwen/qwen3.8-27b") == {"reasoning_format": "hidden"}
    assert model_options("other") == {}
