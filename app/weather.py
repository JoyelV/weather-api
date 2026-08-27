import httpx
from pydantic import BaseModel, ValidationError

from app.models import WeatherData


WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


# Why the upstream call failed, so the API layer can pick a status code.
NOT_FOUND = "not_found"
UNAVAILABLE = "unavailable"

class _Location(BaseModel):
    """The part of an Open-Meteo geocoding hit this service relies on."""

    name: str
    country: str
    latitude: float
    longitude: float


def get_weather(city: str):
    # 1. Find the city
    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"

    geocoding_params = {
        "name": city,
        "count": 10,
        "language": "en",
        "format": "json",
        "countryCode": "IN",
    }

    try:
        geocoding_response = httpx.get(
            geocoding_url,
            params=geocoding_params,
            timeout=10.0,
        )
        geocoding_response.raise_for_status()
    except httpx.RequestError:
        return {
            "error": "Weather service is currently unavailable.",
            "reason": UNAVAILABLE,
        }
    except httpx.HTTPStatusError:
        return {
            "error": "Weather service returned an error.",
            "reason": UNAVAILABLE,
        }

    try:
        geocoding_data = geocoding_response.json()
    except ValueError:
        return {
            "error": "Weather service returned an invalid response.",
            "reason": UNAVAILABLE,
        }

    if not isinstance(geocoding_data, dict):
        return {
            "error": "Weather service returned an invalid response.",
            "reason": UNAVAILABLE,
        }

    results = geocoding_data.get("results")

    # Open-Meteo omits "results" entirely for a miss.
    if results is None:
        return {
            "error": f"Could not find {city}",
            "reason": NOT_FOUND,
        }

    if not isinstance(results, list):
        return {
            "error": "Weather service returned an invalid response.",
            "reason": UNAVAILABLE,
        }

    # A known-empty result set is still just a miss.
    if not results:
        return {
            "error": f"Could not find {city}",
            "reason": NOT_FOUND,
        }

    if not isinstance(results[0], dict):
        return {
            "error": "Weather service returned an invalid response.",
            "reason": UNAVAILABLE,
        }

    try:
        location = _Location.model_validate(results[0])
    except ValidationError:
        return {
            "error": "Weather service returned an invalid response.",
            "reason": UNAVAILABLE,
        }

    latitude = location.latitude
    longitude = location.longitude

    # 2. Get current weather
    weather_url = "https://api.open-meteo.com/v1/forecast"

    weather_params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "weather_code,"
            "wind_speed_10m"
        ),
        "timezone": "auto",
    }

    try:
        weather_response = httpx.get(
            weather_url,
            params=weather_params,
            timeout=10.0,
        )
        weather_response.raise_for_status()
    except httpx.RequestError:
        return {
            "error": "Weather service is currently unavailable.",
            "reason": UNAVAILABLE,
        }
    except httpx.HTTPStatusError:
        return {
            "error": "Weather service returned an error.",
            "reason": UNAVAILABLE,
        }

    try:
        weather_data = weather_response.json()
    except ValueError:
        return {
            "error": "Weather service returned an invalid response.",
            "reason": UNAVAILABLE,
        }

    # 3. Add human-readable weather condition
    if not isinstance(weather_data, dict) or not isinstance(
        weather_data.get("current"), dict
    ):
        return {
            "error": "Weather service returned an invalid response.",
            "reason": UNAVAILABLE,
        }

    try:
        # "condition" is derived below; the placeholder completes the model.
        validated = WeatherData.model_validate(
            {**weather_data["current"], "condition": ""}
        )
    except ValidationError:
        return {
            "error": "Weather service returned an invalid response.",
            "reason": UNAVAILABLE,
        }

    weather = validated.model_dump()

    weather["condition"] = WEATHER_CODES.get(
        validated.weather_code,
        "Unknown",
    )

    # 4. Return the result
    return {
        "city": location.name,
        "country": location.country,
        "latitude": latitude,
        "longitude": longitude,
        "weather": weather,
    }