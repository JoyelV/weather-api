from pydantic import BaseModel


class WeatherData(BaseModel):
    time: str
    interval: int
    temperature_2m: float
    relative_humidity_2m: int
    apparent_temperature: float
    weather_code: int
    wind_speed_10m: float
    condition: str


class WeatherResponse(BaseModel):
    city: str
    country: str
    latitude: float
    longitude: float
    weather: WeatherData
    explanation: str