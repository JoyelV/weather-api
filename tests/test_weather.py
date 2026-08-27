import httpx

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
        "error": "Could not find xxxxxxxxxxxx"
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
        "error": "Weather service is currently unavailable."
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
        "error": "Weather service returned an error."
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
        "error": "Weather service returned an invalid response."
    }

def test_ai_service_unavailable():
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

    assert response.status_code == 503
    assert response.json() == {
        "detail": "AI weather service is currently unavailable."
    }