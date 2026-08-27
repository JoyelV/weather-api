from fastapi import FastAPI, HTTPException, Query
from app.weather import NOT_FOUND, get_weather
from app.llm import explain_weather
from app.models import WeatherResponse

app = FastAPI(
    title="Weather AI API",
    description="A FastAPI service that retrieves weather data and generates AI-powered weather explanations.",
    version="1.0.0",
)

@app.get("/")
def home():
    return {
        "message": "Weather AI API is running!"
    }


@app.get("/weather", response_model=WeatherResponse)
def weather(city: str = Query(..., min_length=1)):
    city = city.strip()

    if not city:
        raise HTTPException(
         status_code=422,
         detail="City cannot be empty."
       )
    weather_data = get_weather(city)

    if "error" in weather_data:
        # A missing city is a 404; an upstream failure is not the caller's fault.
        if weather_data.get("reason") == NOT_FOUND:
            status_code = 404
        else:
            status_code = 503

        raise HTTPException(
            status_code=status_code,
            detail=weather_data["error"]
        )

    try:
        explanation = explain_weather(weather_data)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="AI weather service is currently unavailable."
        )

    return {
        "city": weather_data["city"],
        "country": weather_data["country"],
        "latitude": weather_data["latitude"],
        "longitude": weather_data["longitude"],
        "weather": weather_data["weather"],
        "explanation": explanation,
    }