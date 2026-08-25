from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_home():
    response = client.get("/")

    assert response.status_code == 200


def test_weather_endpoint():
    with patch(
        "app.main.explain_weather"
    ) as mock_explain:

        mock_explain.return_value = (
            "Kochi is 25°C with moderate drizzle."
        )

        response = client.get(
            "/weather?city=Kochi"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["city"] == "Kochi"
    assert data["country"] == "India"
    assert "weather" in data
    assert "explanation" in data

    assert data["explanation"] == (
        "Kochi is 25°C with moderate drizzle."
    )


def test_invalid_city_endpoint():
    response = client.get(
        "/weather?city=xxxxxxxxxxxx"
    )

    assert response.status_code == 404