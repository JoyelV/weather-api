# Weather AI API

A weather app built with Python, FastAPI, LangChain, and Google Gemini.

The application fetches real-time weather data from [Open-Meteo](https://open-meteo.com/)
and uses Google Gemini (through LangChain) to turn that data into a simple,
human-readable weather explanation. It ships with a small browser front end that
renders the reading and the explanation together.

## Features

- Browser front end served by the API itself, with loading, empty and error states
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
- Vanilla HTML, CSS and JavaScript (no build step)
- pytest
- Docker

## Project Structure

```text
weather-api/
├── app/
│   ├── main.py      # FastAPI app, routes and static file mount
│   ├── weather.py   # Open-Meteo geocoding and weather calls
│   ├── llm.py       # LangChain + Google Gemini explanation
│   └── models.py    # Pydantic response models
├── frontend/
│   ├── index.html   # Page markup
│   ├── styles.css   # Styles
│   └── app.js       # Fetches /weather and renders the reading
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

> **Note on Gemini quotas.** The free tier allows a limited number of
> `generateContent` requests per day. Once that quota is used up, Gemini returns
> `429 RESOURCE_EXHAUSTED` and `/weather` responds with `503` until the quota
> resets. See https://ai.google.dev/gemini-api/docs/rate-limits for current limits.

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

## Running the App

Start the development server with Uvicorn:

```bash
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000 in a browser for the web interface.

FastAPI also serves interactive API documentation at http://127.0.0.1:8000/docs.

## Web Interface

The front end in `frontend/` is plain HTML, CSS and JavaScript with no build step.
`app/main.py` mounts it with Starlette's `StaticFiles`, so the same Uvicorn process
serves both the UI and the API and there is no CORS configuration to manage.

The page takes a city name, calls `GET /weather`, and renders the current reading —
temperature, condition, feels-like, humidity and wind — alongside the Gemini
explanation. It also has a loading skeleton, an empty state, and per-status error
states for `404`, `422` and `503`.

## API Endpoints

### `GET /`

Serves the web interface (`frontend/index.html`).

### `GET /health`

A simple health check that confirms the service is running.

```bash
curl "http://127.0.0.1:8000/health"
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
`requirements.txt`, copies the `app` package and the `frontend` directory, exposes port
`8000`, and starts Uvicorn.

Build the image:

```bash
docker build -t weather-api .
```

Run the container, passing your `.env` file so the app can read `GOOGLE_API_KEY`:

```bash
docker run --env-file .env -p 8000:8000 weather-api
```

The app is then available at http://127.0.0.1:8000.

## How It Works

1. The browser loads the front end from `/`, served by the static file mount in
   `app/main.py`, and `frontend/app.js` calls `GET /weather?city=<city>`.
2. `app/weather.py` geocodes the city with the Open-Meteo geocoding API to get its
   latitude and longitude, then requests the current weather from the Open-Meteo
   forecast API and maps the numeric weather code to a readable condition.
3. `app/llm.py` builds a LangChain prompt from that weather data and sends it to Google
   Gemini, which returns a short plain-language explanation.
4. `app/main.py` combines the weather data and the explanation into a `WeatherResponse`
   defined in `app/models.py` and returns it as JSON.
5. `frontend/app.js` renders that payload as the reading card, or renders a matching
   error state if the request failed.
