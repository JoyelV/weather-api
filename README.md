# Weather AI API

A beginner-friendly weather API built with Python, FastAPI, LangChain, and Google Gemini.

The application fetches real-time weather data from [Open-Meteo](https://open-meteo.com/)
and uses Google Gemini (through LangChain) to turn that data into a simple,
human-readable weather explanation.

## Features

- Look up current weather by city name
- Geocode Indian cities using the Open-Meteo geocoding API
- Return temperature, feels-like temperature, humidity, wind speed and weather code
- Convert numeric weather codes into readable conditions (for example, `53` becomes "Moderate drizzle")
- Generate an AI-written weather explanation with Google Gemini via LangChain
- Validate responses with Pydantic models
- Automated tests with pytest
- Docker support

## Tech Stack

- Python 3.13
- FastAPI
- Uvicorn
- LangChain (`langchain-google-genai`)
- Google Gemini
- Open-Meteo (weather and geocoding data)
- httpx
- Pydantic
- pytest
- Docker

## Project Structure

```text
weather-api/
├── app/
│   ├── main.py      # FastAPI app and routes
│   ├── weather.py   # Open-Meteo geocoding and weather calls
│   ├── llm.py       # LangChain + Google Gemini explanation
│   └── models.py    # Pydantic response models
├── tests/
│   └── test_weather.py
├── .github/
│   └── workflows/
│       └── tests.yml
├── .dockerignore
├── .env             # not committed
├── .gitignore
├── Dockerfile
├── README.md
└── requirements.txt
```

## Prerequisites

- Python 3.13
- A Google Gemini API key (create one at https://aistudio.google.com/app/apikey)
- Docker, if you want to run the app in a container

## Environment Variables

The app reads its configuration from a `.env` file in the project root, loaded with
`python-dotenv`.

Create a `.env` file containing:

```text
GOOGLE_API_KEY=your-google-api-key-here
```

`GOOGLE_API_KEY` is the only environment variable the application uses. `.env` is listed
in `.gitignore` and `.dockerignore`, so your key is never committed or copied into the
Docker image.

## Local Development Setup

1. Clone the repository and move into it:

```bash
git clone <repository-url>
```

```bash
cd weather-api
```

2. Create and activate a virtual environment.

On Windows (PowerShell):

```bash
python -m venv venv
```

```bash
venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
python -m venv venv
```

```bash
source venv/bin/activate
```

3. Install the dependencies:

```bash
pip install -r requirements.txt
```

4. Create your `.env` file as described in [Environment Variables](#environment-variables).

## Running the API

Start the development server with Uvicorn:

```bash
uvicorn app.main:app --reload
```

The API is then available at http://127.0.0.1:8000.

FastAPI also serves interactive documentation at http://127.0.0.1:8000/docs.

## API Endpoints

### `GET /`

A simple health check that confirms the service is running.

```bash
curl "http://127.0.0.1:8000/"
```

```json
{
  "message": "Weather AI API is running!"
}
```

### `GET /weather?city=Kochi`

Returns the current weather for a city, along with an AI-generated explanation.

**Query parameters**

| Name   | Type   | Required | Description                                  |
| ------ | ------ | -------- | -------------------------------------------- |
| `city` | string | Yes      | City name to look up. Must not be empty.      |

City lookup is performed through Open-Meteo's geocoding API and is restricted to
cities in India.

**Example request**

```bash
curl "http://127.0.0.1:8000/weather?city=Kochi"
```

**Example response**

```json
{
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
    "condition": "Moderate drizzle"
  },
  "explanation": "In Kochi, India, it is currently 25.2°C and feels like 30.8°C, with moderate drizzle, 94% humidity and a wind speed of 3.6 km/h."
}
```

**Status codes**

| Code  | Meaning                                                                 |
| ----- | ----------------------------------------------------------------------- |
| `200` | Weather data and explanation returned successfully                       |
| `404` | The city could not be found                                              |
| `422` | The `city` parameter is missing, empty, or only whitespace               |
| `503` | The weather service or the AI service is unavailable                     |

## Running Tests

With your virtual environment active, run the test suite from the project root:

```bash
python -m pytest
```

The tests use FastAPI's `TestClient` and mock out both the Open-Meteo calls and the
Gemini call, so no API key or network access is required to run them.

The same command runs automatically on every push and pull request to `main` through
the GitHub Actions workflow in `.github/workflows/tests.yml`.

## Docker

The included `Dockerfile` builds on `python:3.13-slim`, installs the dependencies from
`requirements.txt`, copies the `app` package, exposes port `8000`, and starts Uvicorn.

Build the image:

```bash
docker build -t weather-api .
```

Run the container, passing your `.env` file so the app can read `GOOGLE_API_KEY`:

```bash
docker run --env-file .env -p 8000:8000 weather-api
```

The API is then available at http://127.0.0.1:8000.

## How It Works

1. A request arrives at `GET /weather?city=<city>` in `app/main.py`.
2. `app/weather.py` geocodes the city with the Open-Meteo geocoding API to get its
   latitude and longitude, then requests the current weather from the Open-Meteo
   forecast API and maps the numeric weather code to a readable condition.
3. `app/llm.py` builds a LangChain prompt from that weather data and sends it to Google
   Gemini, which returns a short plain-language explanation.
4. `app/main.py` combines the weather data and the explanation into a `WeatherResponse`
   defined in `app/models.py` and returns it as JSON.
