"""Tests for the Gemini -> Groq LLM provider fallback in app.llm."""

import logging
import os
import subprocess
import sys
import tempfile
import textwrap

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fastapi.testclient import TestClient

from app.llm import explain_weather
from app.main import app


client = TestClient(app)


WEATHER_DATA = {
    "city": "Kochi",
    "country": "India",
    "latitude": 9.93988,
    "longitude": 76.26022,
    "weather": {
        "time": "2026-08-25T23:00",
        "interval": 900,
        "temperature_2m": 25.2,
        "relative_humidity_2m": 94,
        "apparent_temperature": 30.8,
        "weather_code": 53,
        "wind_speed_10m": 3.6,
        "condition": "Moderate drizzle",
    },
}


def _fake_client(content):
    """A stand-in chat model whose invoke() returns the given content.

    Nothing here touches the network, so no provider quota is consumed.
    """
    fake = MagicMock()
    fake.invoke.return_value = MagicMock(content=content)
    return fake


def test_gemini_success_does_not_reach_groq():
    gemini = _fake_client("Kochi is 25.2°C with moderate drizzle.")
    groq = _fake_client("groq answer")

    with patch("app.llm.get_llm", return_value=gemini) as get_llm:
        with patch("app.llm.get_groq_llm", return_value=groq) as get_groq_llm:
            result = explain_weather(WEATHER_DATA)

    get_llm.assert_called_once_with()
    gemini.invoke.assert_called_once()

    get_groq_llm.assert_not_called()
    groq.invoke.assert_not_called()

    assert result == "Kochi is 25.2°C with moderate drizzle."


def test_groq_takes_over_when_gemini_fails(caplog):
    gemini = _fake_client(None)
    gemini.invoke.side_effect = RuntimeError("gemini 503")

    groq = _fake_client("Kochi is 25.2°C with moderate drizzle.")

    with caplog.at_level(logging.WARNING, logger="app.llm"):
        with patch("app.llm.get_llm", return_value=gemini):
            with patch("app.llm.get_groq_llm", return_value=groq):
                result = explain_weather(WEATHER_DATA)

    gemini.invoke.assert_called_once()
    groq.invoke.assert_called_once()

    assert result == "Kochi is 25.2°C with moderate drizzle."
    assert "attempting Groq fallback" in caplog.text


def test_both_providers_failing_raises(caplog):
    gemini = _fake_client(None)
    gemini.invoke.side_effect = RuntimeError("gemini 503")

    groq = _fake_client(None)
    groq.invoke.side_effect = RuntimeError("groq 429")

    with caplog.at_level(logging.WARNING, logger="app.llm"):
        with patch("app.llm.get_llm", return_value=gemini):
            with patch("app.llm.get_groq_llm", return_value=groq):
                with pytest.raises(RuntimeError):
                    explain_weather(WEATHER_DATA)

    gemini.invoke.assert_called_once()
    groq.invoke.assert_called_once()

    assert "attempting Groq fallback" in caplog.text
    assert "Groq weather explanation failed" in caplog.text


def test_both_providers_failing_returns_the_existing_503():
    """The endpoint keeps its 503 and leaks no provider detail."""
    gemini = _fake_client(None)
    gemini.invoke.side_effect = RuntimeError("gemini quota exhausted")

    groq = _fake_client(None)
    groq.invoke.side_effect = RuntimeError("groq key rejected")

    with patch("app.main.get_weather", return_value=WEATHER_DATA):
        with patch("app.llm.get_llm", return_value=gemini):
            with patch("app.llm.get_groq_llm", return_value=groq):
                response = client.get("/weather", params={"city": "Kochi"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "AI weather service is currently unavailable."
    }

    assert "gemini quota exhausted" not in response.text
    assert "groq key rejected" not in response.text
    assert "RuntimeError" not in response.text


def test_both_providers_receive_the_same_prompt():
    gemini = _fake_client(None)
    gemini.invoke.side_effect = RuntimeError("gemini down")

    groq = _fake_client("fallback explanation")

    with patch("app.llm.get_llm", return_value=gemini):
        with patch("app.llm.get_groq_llm", return_value=groq):
            explain_weather(WEATHER_DATA)

    gemini_messages = gemini.invoke.call_args.args[0]
    groq_messages = groq.invoke.call_args.args[0]

    assert [(m.type, m.content) for m in gemini_messages] == [
        (m.type, m.content) for m in groq_messages
    ]

    system, human = gemini_messages

    assert system.type == "system"
    assert "You are a helpful weather assistant." in system.content

    assert human.type == "human"
    for value in ("Kochi", "India", "25.2", "30.8", "94", "3.6",
                  "Moderate drizzle"):
        assert value in human.content


@pytest.mark.parametrize("answering_provider", ["gemini", "groq"])
def test_string_response_is_returned_as_is(answering_provider):
    """The string path is preserved on whichever provider answers."""
    gemini = _fake_client("plain string answer")
    groq = _fake_client("plain string answer")

    # Groq only ever answers after Gemini has failed, so the Groq case has
    # to knock Gemini out or the fallback path is never reached.
    if answering_provider == "groq":
        gemini.invoke.side_effect = RuntimeError("gemini down")

    with patch("app.llm.get_llm", return_value=gemini):
        with patch("app.llm.get_groq_llm", return_value=groq):
            assert explain_weather(WEATHER_DATA) == "plain string answer"

    # Guards against the parametrisation silently testing Gemini twice.
    assert groq.invoke.called is (answering_provider == "groq")


@pytest.mark.parametrize("answering_provider", ["gemini", "groq"])
def test_multipart_response_is_joined(answering_provider):
    """The list path is preserved on whichever provider answers."""
    multipart = [
        {"type": "text", "text": " Kochi is 25.2°C"},
        {"type": "image", "url": "https://example.com/x.png"},
        {"type": "text", "text": " with moderate drizzle. "},
        "not a dict",
    ]

    gemini = _fake_client(multipart)
    groq = _fake_client(multipart)

    # Groq only ever answers after Gemini has failed, so the Groq case has
    # to knock Gemini out or the fallback path is never reached.
    if answering_provider == "groq":
        gemini.invoke.side_effect = RuntimeError("gemini down")

    with patch("app.llm.get_llm", return_value=gemini):
        with patch("app.llm.get_groq_llm", return_value=groq):
            result = explain_weather(WEATHER_DATA)

    assert result == "Kochi is 25.2°C with moderate drizzle."

    # Guards against the parametrisation silently testing Gemini twice.
    assert groq.invoke.called is (answering_provider == "groq")


def test_neither_client_is_built_without_api_keys():
    """Importing app.llm must not construct Gemini or Groq.

    Both keys are stripped from the subprocess environment and the working
    directory is the system temp directory, so the repository .env is not
    discovered and no real provider call can be made.
    """
    project_root = Path(__file__).resolve().parents[1]

    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY")
    }
    env["PYTHONPATH"] = str(project_root)

    code = textwrap.dedent(
        """
        import os

        for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
            assert name not in os.environ, name

        import app.main
        from app.llm import get_groq_llm, get_llm

        # A .env on disk must not quietly re-supply a key and mask a failure.
        for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
            assert name not in os.environ, name + " got loaded"

        # Neither client may be built as a side effect of importing.
        assert get_llm.cache_info().currsize == 0, "Gemini built at import time"
        assert get_groq_llm.cache_info().currsize == 0, "Groq built at import time"

        print("IMPORT_OK")
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tempfile.gettempdir(),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "IMPORT_OK" in result.stdout


def test_groq_client_is_cached_and_reads_the_key_from_the_environment():
    """get_groq_llm builds on first call, then reuses the same client."""
    from app.llm import get_groq_llm

    get_groq_llm.cache_clear()

    try:
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
            with patch("app.llm.ChatGroq") as chat_groq:
                first = get_groq_llm()
                second = get_groq_llm()

        chat_groq.assert_called_once_with(
            model="llama-3.1-8b-instant",
            api_key="test-key",
        )
        assert first is second
        assert get_groq_llm.cache_info().currsize == 1
    finally:
        get_groq_llm.cache_clear()


def test_fallback_without_a_groq_api_key_fails_closed():
    """The state of any deployment that has not added GROQ_API_KEY yet.

    get_groq_llm is deliberately left unpatched so the real ChatGroq
    constructor runs and raises on the missing key. Construction is purely
    local -- no client is ever built, so no request reaches either provider.
    """
    from app.llm import get_groq_llm

    gemini = _fake_client(None)
    gemini.invoke.side_effect = RuntimeError("gemini down")

    get_groq_llm.cache_clear()

    try:
        with patch.dict(os.environ):
            os.environ.pop("GROQ_API_KEY", None)

            with patch("app.llm.get_llm", return_value=gemini):
                # explain_weather surfaces the construction failure ...
                with pytest.raises(Exception) as excinfo:
                    explain_weather(WEATHER_DATA)

                # Proves the failure is Groq's missing-key construction error,
                # not the Gemini error leaking through untouched.
                assert "api_key" in str(excinfo.value).lower()

                # ... and the endpoint turns it into the existing 503.
                with patch("app.main.get_weather", return_value=WEATHER_DATA):
                    response = client.get("/weather", params={"city": "Kochi"})

        assert gemini.invoke.call_count == 2

        assert response.status_code == 503
        assert response.json() == {
            "detail": "AI weather service is currently unavailable."
        }

        # No key name, key value, or provider internals reach the caller.
        for leak in ("GROQ_API_KEY", "api_key", "GroqError", "gemini down"):
            assert leak not in response.text

        # A failed construction must not be memoised as a usable client.
        assert get_groq_llm.cache_info().currsize == 0
    finally:
        get_groq_llm.cache_clear()
