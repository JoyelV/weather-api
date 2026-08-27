import httpx


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
            "error": "Weather service is currently unavailable."
        }
    except httpx.HTTPStatusError:
        return {
            "error": "Weather service returned an error."
        }

    try:
        geocoding_data = geocoding_response.json()
    except ValueError:
        return {
             "error": "Weather service returned an invalid response."
        }

    if "results" not in geocoding_data:
        return {
            "error": f"Could not find {city}"
        }

    location = geocoding_data["results"][0]

    latitude = location["latitude"]
    longitude = location["longitude"]

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
            "error": "Weather service is currently unavailable."
        }
    except httpx.HTTPStatusError:
        return {
            "error": "Weather service returned an error."
        }

    try:
        weather_data = weather_response.json()
    except ValueError:
        return {
            "error": "Weather service returned an invalid response."
       }

    # 3. Add human-readable weather condition
    weather = weather_data["current"]

    weather["condition"] = WEATHER_CODES.get(
        weather["weather_code"],
        "Unknown",
    )

    # 4. Return the result
    return {
        "city": location["name"],
        "country": location["country"],
        "latitude": latitude,
        "longitude": longitude,
        "weather": weather,
    }