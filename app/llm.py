import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate


load_dotenv()


@lru_cache(maxsize=1)
def get_llm() -> ChatGoogleGenerativeAI:
    """Create the Gemini client on first use, then reuse it.

    Building the client at import time would require GOOGLE_API_KEY
    just to import this module.
    """
    return ChatGoogleGenerativeAI(
        model="gemini-3.6-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )


prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are a helpful weather assistant.

Explain weather information in simple, natural language.

Rules:
- Be concise and beginner-friendly.
- Only describe the information provided above.
- Do not invent, assume, or infer information.
- Do not mention seasons, monsoons, or typical weather.
- Do not give recommendations or advice.
- Do not tell the user what they should wear or carry.
- Mention the city.
- Mention temperature.
- Mention feels-like temperature.
- Mention humidity.
- Mention wind speed.
- Mention the weather condition.
- Do not mention the numeric weather code.
"""
    ),
    (
        "human",
        """
Give me a weather summary for:

City: {city}
Country: {country}

Temperature: {temperature}°C
Feels like: {feels_like}°C
Humidity: {humidity}%
Wind speed: {wind_speed} km/h
Condition: {condition}
"""
    ),
])


def explain_weather(weather_data: dict):
    weather = weather_data["weather"]

    messages = prompt.format_messages(
        city=weather_data["city"],
        country=weather_data["country"],
        temperature=weather["temperature_2m"],
        feels_like=weather["apparent_temperature"],
        humidity=weather["relative_humidity_2m"],
        wind_speed=weather["wind_speed_10m"],
        condition=weather["condition"],
    )

    response = get_llm().invoke(messages)

    content = response.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "".join(text_parts).strip()

    return str(content)