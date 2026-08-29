import json
import os
import subprocess
import sys
import tempfile
import textwrap

import httpx
import pytest

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.weather import get_weather


client = TestClient(app)


def test_home():
    response = client.get("/")

    assert response.status_code == 200


def test_weather_endpoint():
    fake_weather = {
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

    with patch("app.main.get_weather") as mock_weather:
        with patch("app.main.explain_weather") as mock_explain:
            mock_weather.return_value = fake_weather

            mock_explain.return_value = (
                "Kochi is 25.2°C with moderate drizzle."
            )

            response = client.get(
                "/weather?city=Kochi"
            )

            mock_weather.assert_called_once_with("Kochi")
            mock_explain.assert_called_once_with(fake_weather)

    assert response.status_code == 200

    data = response.json()

    assert data["city"] == "Kochi"
    assert data["country"] == "India"
    assert data["weather"]["condition"] == "Moderate drizzle"
    assert data["explanation"] == (
        "Kochi is 25.2°C with moderate drizzle."
    )


def test_invalid_city_endpoint():
    fake_error = {
        "error": "Could not find xxxxxxxxxxxx",
        "reason": "not_found",
    }

    with patch("app.main.get_weather") as mock_weather:
        with patch("app.main.explain_weather") as mock_explain:
            mock_weather.return_value = fake_error

            response = client.get(
                "/weather?city=xxxxxxxxxxxx"
            )

            mock_weather.assert_called_once_with("xxxxxxxxxxxx")
            mock_explain.assert_not_called()

    assert response.status_code == 404

def test_empty_city():
    response = client.get("/weather?city=")

    assert response.status_code == 422

def test_whitespace_city():
    with patch("app.main.get_weather") as mock_weather:
        with patch("app.main.explain_weather") as mock_explain:
            response = client.get(
                "/weather",
                params={"city": "   "}
            )

            mock_weather.assert_not_called()
            mock_explain.assert_not_called()

    assert response.status_code == 422

def test_weather_service_network_error():
    with patch(
        "app.weather.httpx.get",
        side_effect=httpx.RequestError("Connection failed"),
    ):
        result = get_weather("Kochi")

    assert result == {
        "error": "Weather service is currently unavailable.",
        "reason": "unavailable",
    }

def test_weather_service_http_error():
    mock_response = httpx.Response(
        status_code=500,
        request=httpx.Request(
            "GET",
            "https://example.com",
        ),
    )

    with patch(
        "app.weather.httpx.get",
        return_value=mock_response,
    ):
        result = get_weather("Kochi")

    assert result == {
        "error": "Weather service returned an error.",
        "reason": "unavailable",
    }

def test_weather_service_invalid_json():
    mock_response = httpx.Response(
        status_code=200,
        content=b"this is not valid json",
        request=httpx.Request(
            "GET",
            "https://example.com",
        ),
    )

    with patch(
        "app.weather.httpx.get",
        return_value=mock_response,
    ):
        result = get_weather("Kochi")

    assert result == {
        "error": "Weather service returned an invalid response.",
        "reason": "unavailable",
    }

def test_ai_service_unavailable_degrades_gracefully():
    fake_weather = {
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

    with patch("app.main.get_weather") as mock_weather:
        with patch("app.main.explain_weather") as mock_explain:
            mock_weather.return_value = fake_weather
            mock_explain.side_effect = Exception("AI service failed")

            response = client.get(
                "/weather",
                params={"city": "Kochi"},
            )

            mock_weather.assert_called_once_with("Kochi")
            mock_explain.assert_called_once_with(fake_weather)

    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "Kochi"
    assert data["country"] == "India"
    assert data["weather"]["condition"] == "Moderate drizzle"
    assert data["weather"]["temperature_2m"] == 25.2
    assert data["explanation"] == (
        "Current weather data is available, but the AI explanation service is temporarily unavailable."
    )


def test_app_imports_without_gemini_api_key():
    """app.main must import when no Gemini API key is present.

    Regression test: app/llm.py used to build ChatGoogleGenerativeAI at module
    import time, so importing app.main raised a pydantic ValidationError
    wherever GOOGLE_API_KEY was unset. That broke pytest collection in CI
    before a single test could run.

    The import happens in a fresh subprocess whose working directory is the
    system temp directory, so the repository .env is not discovered and no
    real Gemini call is ever made.
    """
    project_root = Path(__file__).resolve().parents[1]

    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("GOOGLE_API_KEY", "GEMINI_API_KEY")
    }
    env["PYTHONPATH"] = str(project_root)

    code = textwrap.dedent(
        """
        import os

        assert "GOOGLE_API_KEY" not in os.environ
        assert "GEMINI_API_KEY" not in os.environ

        import app.main
        from app.llm import get_llm

        # A .env on disk must not quietly re-supply the key and mask a failure.
        assert "GOOGLE_API_KEY" not in os.environ, "GOOGLE_API_KEY got loaded"
        assert "GEMINI_API_KEY" not in os.environ, "GEMINI_API_KEY got loaded"

        # The client must not be built as a side effect of importing.
        assert get_llm.cache_info().currsize == 0, "client built at import time"

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


CURRENT_OK = {
    "time": "2026-08-25T23:00",
    "interval": 900,
    "temperature_2m": 25.2,
    "relative_humidity_2m": 94,
    "apparent_temperature": 30.8,
    "weather_code": 53,
    "wind_speed_10m": 3.6,
}

GEOCODING_OK = {
    "results": [
        {
            "name": "Kochi",
            "country": "India",
            "latitude": 9.93988,
            "longitude": 76.26022,
        }
    ]
}


def _json_response(payload, status_code=200):
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(payload).encode(),
        request=httpx.Request("GET", "https://example.com"),
    )


@pytest.mark.parametrize(
    "error",
    [
        httpx.RequestError("Connection failed"),
        httpx.TimeoutException("Timed out"),
    ],
)
def test_upstream_unreachable_returns_503(error):
    """A network failure or timeout is an upstream fault, not a missing city."""
    with patch("app.weather.httpx.get", side_effect=error):
        with patch("app.main.explain_weather") as mock_explain:
            response = client.get("/weather", params={"city": "Kochi"})

            mock_explain.assert_not_called()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Weather service is currently unavailable."
    }


def test_upstream_http_error_returns_503():
    with patch(
        "app.weather.httpx.get",
        return_value=_json_response({}, status_code=500),
    ):
        with patch("app.main.explain_weather") as mock_explain:
            response = client.get("/weather", params={"city": "Kochi"})

            mock_explain.assert_not_called()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Weather service returned an error."
    }


def test_upstream_invalid_json_returns_503():
    mock_response = httpx.Response(
        status_code=200,
        content=b"this is not valid json",
        request=httpx.Request("GET", "https://example.com"),
    )

    with patch("app.weather.httpx.get", return_value=mock_response):
        with patch("app.main.explain_weather") as mock_explain:
            response = client.get("/weather", params={"city": "Kochi"})

            mock_explain.assert_not_called()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Weather service returned an invalid response."
    }


@pytest.mark.parametrize(
    "geocoding_payload",
    [
        {},
        {"results": []},
    ],
)
def test_city_not_found_returns_404(geocoding_payload):
    """Open-Meteo omits "results" for a miss, but may also return an empty list."""
    with patch(
        "app.weather.httpx.get",
        return_value=_json_response(geocoding_payload),
    ):
        with patch("app.main.explain_weather") as mock_explain:
            response = client.get("/weather", params={"city": "Kochi"})

            mock_explain.assert_not_called()

    assert response.status_code == 404
    assert response.json() == {"detail": "Could not find Kochi"}


@pytest.mark.parametrize(
    "geocoding_payload, forecast_payload",
    [
        ([1, 2], None),
        ({"results": [{"name": "Kochi", "latitude": 9.9, "longitude": 76.2}]},
         {"current": CURRENT_OK}),
        (GEOCODING_OK, {"hourly": {}}),
        (GEOCODING_OK, {"current": {"temperature_2m": 25.2}}),
        (GEOCODING_OK, {"current": {k: v for k, v in CURRENT_OK.items()
                                    if k not in ("time", "interval")}}),
    ],
    ids=[
        "geocoding-not-an-object",
        "location-missing-country",
        "forecast-missing-current",
        "current-missing-weather-code",
        "current-missing-time-and-interval",
    ],
)
def test_malformed_upstream_payload_returns_503(
    geocoding_payload, forecast_payload
):
    """Incomplete upstream data must not surface as an unhandled 500."""
    responses = [_json_response(geocoding_payload)]

    if forecast_payload is not None:
        responses.append(_json_response(forecast_payload))

    with patch("app.weather.httpx.get", side_effect=responses):
        with patch("app.main.explain_weather") as mock_explain:
            response = client.get("/weather", params={"city": "Kochi"})

            mock_explain.assert_not_called()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Weather service returned an invalid response."
    }


def test_valid_city_response_shape_is_unchanged():
    """The successful payload must keep its exact structure."""
    responses = [
        _json_response(GEOCODING_OK),
        _json_response({"current": dict(CURRENT_OK)}),
    ]

    with patch("app.weather.httpx.get", side_effect=responses):
        with patch("app.main.explain_weather", return_value="Kochi is mild."):
            response = client.get("/weather", params={"city": "Kochi"})

    assert response.status_code == 200
    assert response.json() == {
        "city": "Kochi",
        "country": "India",
        "latitude": 9.93988,
        "longitude": 76.26022,
        "weather": {**CURRENT_OK, "condition": "Moderate drizzle"},
        "explanation": "Kochi is mild.",
    }


@pytest.mark.parametrize(
    "geocoding_payload, forecast_payload",
    [
        ({"results": {"a": 1}}, None),
        ({"results": 5}, None),
        ({"results": [[1]]}, None),
        ({"results": ["x"]}, None),
        ({"results": [None]}, None),
        (GEOCODING_OK, {"current": {**CURRENT_OK, "temperature_2m": "hot"}}),
        (GEOCODING_OK, {"current": {**CURRENT_OK, "relative_humidity_2m": 94.5}}),
        (GEOCODING_OK, {"current": {**CURRENT_OK, "time": None}}),
        (GEOCODING_OK, {"current": {**CURRENT_OK, "weather_code": [1]}}),
    ],
    ids=[
        "results-is-an-object",
        "results-is-an-integer",
        "results-first-item-is-a-list",
        "results-first-item-is-a-string",
        "results-first-item-is-null",
        "temperature-is-a-string",
        "humidity-is-a-float",
        "time-is-null",
        "weather-code-is-a-list",
    ],
)
def test_wrongly_typed_upstream_payload_returns_503(
    geocoding_payload, forecast_payload
):
    """Wrong types must be rejected before FastAPI validates the response."""
    responses = [_json_response(geocoding_payload)]

    if forecast_payload is not None:
        responses.append(_json_response(forecast_payload))

    with patch("app.weather.httpx.get", side_effect=responses):
        with patch("app.main.explain_weather") as mock_explain:
            response = client.get("/weather", params={"city": "Kochi"})

            mock_explain.assert_not_called()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Weather service returned an invalid response."
    }


@pytest.mark.parametrize(
    "location_payload",
    [
        {"name": "Kochi", "country": "India", "latitude": "abc", "longitude": 76.2},
        {"name": "Kochi", "country": "India", "latitude": None, "longitude": 76.2},
        {"name": [1], "country": "India", "latitude": 9.9, "longitude": 76.2},
        {"name": "Kochi", "country": 7, "latitude": 9.9, "longitude": 76.2},
    ],
    ids=[
        "latitude-is-a-string",
        "latitude-is-null",
        "name-is-a-list",
        "country-is-an-integer",
    ],
)
def test_wrongly_typed_location_returns_503(location_payload):
    """A malformed geocoding hit must fail before the AI call, not after it."""
    responses = [
        _json_response({"results": [location_payload]}),
        _json_response({"current": dict(CURRENT_OK)}),
    ]

    with patch("app.weather.httpx.get", side_effect=responses):
        with patch("app.main.explain_weather") as mock_explain:
            response = client.get("/weather", params={"city": "Kochi"})

            mock_explain.assert_not_called()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Weather service returned an invalid response."
    }


@pytest.mark.parametrize(
    "failure, detail",
    [
        (
            httpx.RequestError("Connection failed"),
            "Weather service is currently unavailable.",
        ),
        (
            httpx.TimeoutException("Timed out"),
            "Weather service is currently unavailable.",
        ),
        (
            "http_status_error",
            "Weather service returned an error.",
        ),
        (
            "invalid_json",
            "Weather service returned an invalid response.",
        ),
    ],
    ids=["request-error", "timeout", "http-status-error", "invalid-json"],
)
def test_forecast_stage_failure_returns_503(failure, detail):
    """The second upstream call has its own handlers; exercise them directly."""
    if failure == "http_status_error":
        second = _json_response({}, status_code=500)
    elif failure == "invalid_json":
        second = httpx.Response(
            status_code=200,
            content=b"this is not valid json",
            request=httpx.Request("GET", "https://example.com"),
        )
    else:
        second = failure

    with patch(
        "app.weather.httpx.get",
        side_effect=[_json_response(GEOCODING_OK), second],
    ):
        with patch("app.main.explain_weather") as mock_explain:
            response = client.get("/weather", params={"city": "Kochi"})

            mock_explain.assert_not_called()

    assert response.status_code == 503
    assert response.json() == {"detail": detail}
