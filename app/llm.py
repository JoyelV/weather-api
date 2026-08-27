import logging
import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate


load_dotenv()

logger = logging.getLogger(__name__)


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


@lru_cache(maxsize=1)
def get_groq_llm() -> ChatGroq:
    """Create the Groq fallback client on first use, then reuse it.

    Cached separately from get_llm so a deployment without GROQ_API_KEY
    still imports and still serves Gemini explanations.
    """
    return ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY"),
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

    try:
        response = get_llm().invoke(messages)
    except Exception:
        # exc_info gives the provider error and traceback; neither carries
        # the API key, which the clients only ever send as a header.
        logger.warning(
            "Gemini weather explanation failed; attempting Groq fallback",
            exc_info=True,
        )

        try:
            # The same formatted messages, so the fallback answers the same
            # prompt under the same system instructions.
            response = get_groq_llm().invoke(messages)
        except Exception:
            logger.error("Groq weather explanation failed", exc_info=True)
            # Both providers are down: raise as before and let the caller
            # turn it into the existing 503.
            raise

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