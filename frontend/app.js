/* ============================================================
   Weather AI — frontend
   Fetches GET /weather?city=... and renders the live response.
   No weather values are hardcoded; everything on screen comes
   from the API payload.
   ============================================================ */

(function () {
  "use strict";

  var form = document.getElementById("search-form");
  var input = document.getElementById("city");
  var button = document.getElementById("search-button");
  var buttonLabel = button.querySelector(".search__button-label");
  var stage = document.getElementById("stage");

  var inFlight = null;

  /* ---------- Condition presentation ----------
     Grouped from weather.weather_code, with weather.condition supplying
     the wording. Each group sets the accent that drives the temperature
     colour, the card rule and the summary rule. */

  var GROUPS = {
    clear:   { accent: "#d98a2b", wash: "rgba(217, 138, 43, 0.10)" },
    cloud:   { accent: "#6b7A91", wash: "rgba(107, 122, 145, 0.10)" },
    fog:     { accent: "#8b9099", wash: "rgba(139, 144, 153, 0.10)" },
    drizzle: { accent: "#3b7fb5", wash: "rgba(59, 127, 181, 0.10)" },
    rain:    { accent: "#2e6fa8", wash: "rgba(46, 111, 168, 0.11)" },
    snow:    { accent: "#5b93bf", wash: "rgba(91, 147, 191, 0.10)" },
    thunder: { accent: "#6b4fa8", wash: "rgba(107, 79, 168, 0.10)" }
  };

  var CODE_GROUPS = {
    0: "clear", 1: "clear",
    2: "cloud", 3: "cloud",
    45: "fog", 48: "fog",
    51: "drizzle", 53: "drizzle", 55: "drizzle",
    61: "rain", 63: "rain", 65: "rain",
    80: "rain", 81: "rain", 82: "rain",
    71: "snow", 73: "snow", 75: "snow",
    95: "thunder", 96: "thunder", 99: "thunder"
  };

  /* Line glyphs drawn to match the instrument feel of the page.
     Deliberately geometric rather than illustrative. */
  var GLYPHS = {
    clear:
      '<circle cx="12" cy="12" r="4"/>' +
      '<path d="M12 3v2.4M12 18.6V21M3 12h2.4M18.6 12H21M5.6 5.6l1.7 1.7M16.7 16.7l1.7 1.7M18.4 5.6l-1.7 1.7M7.3 16.7l-1.7 1.7"/>',
    cloud:
      '<path d="M7.2 18h9.4a3.6 3.6 0 0 0 .4-7.2 5.2 5.2 0 0 0-9.9-1.2A3.7 3.7 0 0 0 7.2 18Z"/>',
    fog:
      '<path d="M7.4 14.5h9.2a3.4 3.4 0 0 0 .4-6.8 5 5 0 0 0-9.5-1.1 3.5 3.5 0 0 0-.1 7.9Z"/>' +
      '<path d="M4.5 18h15M7 21h10"/>',
    drizzle:
      '<path d="M7.2 15.5h9.4a3.6 3.6 0 0 0 .4-7.2 5.2 5.2 0 0 0-9.9-1.2 3.7 3.7 0 0 0 .1 8.4Z"/>' +
      '<path d="M9 18.4v1.4M12.5 18.4v2.6M16 18.4v1.4"/>',
    rain:
      '<path d="M7.2 15.5h9.4a3.6 3.6 0 0 0 .4-7.2 5.2 5.2 0 0 0-9.9-1.2 3.7 3.7 0 0 0 .1 8.4Z"/>' +
      '<path d="M8.6 18.2 7.6 21M12.4 18.2 11.4 21M16.2 18.2 15.2 21"/>',
    snow:
      '<path d="M7.2 15.5h9.4a3.6 3.6 0 0 0 .4-7.2 5.2 5.2 0 0 0-9.9-1.2 3.7 3.7 0 0 0 .1 8.4Z"/>' +
      '<path d="M9 19.4h.01M12.5 18.6h.01M16 19.4h.01M10.6 21.4h.01M14.3 21.4h.01"/>',
    thunder:
      '<path d="M7.2 15h9.4a3.6 3.6 0 0 0 .4-7.2 5.2 5.2 0 0 0-9.9-1.2A3.7 3.7 0 0 0 7.2 15Z"/>' +
      '<path d="m13 17-2.6 3.4h3L11 24"/>'
  };

  function groupFor(code) {
    return CODE_GROUPS[code] || "cloud";
  }

  function glyph(group) {
    return (
      '<svg class="condition__glyph" viewBox="0 0 24 24" width="21" height="21" ' +
      'fill="none" stroke="currentColor" stroke-width="1.6" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      (GLYPHS[group] || GLYPHS.cloud) +
      "</svg>"
    );
  }

  /* ---------- Helpers ---------- */

  function esc(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function round1(n) {
    return (Math.round(Number(n) * 10) / 10).toFixed(1);
  }

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  /* weather.time is already local to the city (timezone=auto upstream),
     so it is read as plain text rather than through Date, which would
     re-interpret it in the browser's zone. */
  function stamp(time) {
    var match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(String(time || ""));

    if (!match) {
      return "Observed just now";
    }

    var month = MONTHS[Number(match[2]) - 1] || "";
    var day = String(Number(match[3]));

    return "Observed " + match[4] + ":" + match[5] + " local · " + day + " " + month;
  }

  function coords(lat, lon) {
    var ns = Number(lat) >= 0 ? "N" : "S";
    var ew = Number(lon) >= 0 ? "E" : "W";

    return (
      Math.abs(Number(lat)).toFixed(3) + "° " + ns + "  /  " +
      Math.abs(Number(lon)).toFixed(3) + "° " + ew
    );
  }

  /* The delta scale uses a fixed 0–50 °C domain so a given temperature
     always lands in the same place, making cities comparable. */
  var SCALE_MIN = 0;
  var SCALE_MAX = 50;

  function scalePosition(value) {
    var pct = ((Number(value) - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)) * 100;
    return Math.max(0, Math.min(100, pct));
  }

  function deltaVerdict(actual, feels) {
    var diff = Number(feels) - Number(actual);
    var size = Math.abs(diff);

    if (size < 0.5) {
      return "Feels about the same as the air temperature.";
    }

    return (
      "Feels <b>" + round1(size) + "°</b> " +
      (diff > 0 ? "warmer" : "cooler") +
      " than the air temperature."
    );
  }

  /* ---------- Error copy ----------
     Maps status codes to something a person can act on. Nothing from a
     stack trace or an internal reason code ever reaches the screen. */

  function detailMessage(payload) {
    if (!payload || typeof payload !== "object") {
      return "";
    }

    var detail = payload.detail;

    if (typeof detail === "string") {
      return detail;
    }

    /* FastAPI's own query validation returns detail as a list of
       objects, so pull the readable message out of the first one. */
    if (Array.isArray(detail) && detail.length) {
      var first = detail[0];

      if (first && typeof first.msg === "string") {
        return first.msg;
      }
    }

    return "";
  }

  function errorFor(status, payload) {
    if (status === 404) {
      return {
        code: "Not found",
        title: "City not found",
        text: "Check the spelling and try again. This service covers cities in India only."
      };
    }

    if (status === 422) {
      return {
        code: "Invalid request",
        title: "That city name won't work",
        text: detailMessage(payload) || "Enter a city name and try again."
      };
    }

    if (status === 503) {
      return {
        code: "Unavailable",
        title: "Weather service is temporarily unavailable",
        text: "The upstream weather or AI service didn't respond. Try again in a moment."
      };
    }

    return {
      code: "Error",
      title: "Something went wrong",
      text: "The reading couldn't be loaded. Try again in a moment."
    };
  }

  /* ---------- Views ---------- */

  function renderEmpty() {
    stage.innerHTML =
      '<div class="empty">' +
        '<div class="empty__mark">' +
          '<svg viewBox="0 0 24 24" width="34" height="34" fill="none" ' +
          'stroke="currentColor" stroke-width="1.3" stroke-linecap="round" aria-hidden="true">' +
            '<circle cx="11" cy="11" r="6.4"/><path d="m16 16 4.5 4.5"/>' +
          "</svg>" +
        "</div>" +
        '<p class="empty__text">Search a city to see its current conditions and a plain-language summary.</p>' +
      "</div>";
  }

  function renderLoading() {
    /* Mirrors the reading card section for section, at the same heights,
       so swapping the result in doesn't move anything on the page. */
    stage.innerHTML =
      '<div class="skeleton" aria-hidden="true">' +
        '<div class="skeleton__head">' +
          '<div class="bone bone--city"></div>' +
          '<div class="bone bone--stamp"></div>' +
        "</div>" +
        '<div class="skeleton__body">' +
          "<div>" +
            '<div class="bone bone--temp"></div>' +
            '<div class="bone bone--cond"></div>' +
          "</div>" +
          '<div class="skeleton__metrics">' +
            '<div class="bone bone--metric"></div>' +
            '<div class="bone bone--metric"></div>' +
            '<div class="bone bone--metric"></div>' +
          "</div>" +
        "</div>" +
        '<div class="skeleton__delta">' +
          '<div class="bone bone--delta-head"></div>' +
          '<div class="bone bone--scale"></div>' +
        "</div>" +
        /* Lines 4 and 5 only show on narrow screens, where the
           explanation wraps to about five lines instead of three. */
        '<div class="skeleton__summary">' +
          '<div class="bone bone--title"></div>' +
          '<div class="bone bone--line"></div>' +
          '<div class="bone bone--line bone--line-2"></div>' +
          '<div class="bone bone--line bone--line-3"></div>' +
          '<div class="bone bone--line bone--line-4"></div>' +
          '<div class="bone bone--line bone--line-5"></div>' +
        "</div>" +
        '<div class="skeleton__foot"></div>' +
      "</div>";
  }

  function renderError(status, payload) {
    var view = errorFor(status, payload);

    stage.innerHTML =
      '<div class="error" role="alert">' +
        '<p class="error__code">' + esc(view.code) + "</p>" +
        '<h3 class="error__title">' + esc(view.title) + "</h3>" +
        '<p class="error__text">' + esc(view.text) + "</p>" +
      "</div>";
  }

  function renderReading(data) {
    var weather = data.weather;
    var group = groupFor(weather.weather_code);
    var theme = GROUPS[group];

    var actualPos = scalePosition(weather.temperature_2m);
    var feelsPos = scalePosition(weather.apparent_temperature);

    stage.innerHTML =
      '<article class="reading" style="--accent:' + theme.accent +
        ";--accent-wash:" + theme.wash + '">' +

        '<header class="reading__head">' +
          '<h3 class="reading__city">' + esc(data.city) +
            '<span class="reading__country">, ' + esc(data.country) + "</span>" +
          "</h3>" +
          '<p class="reading__stamp">' + esc(stamp(weather.time)) + "</p>" +
        "</header>" +

        '<div class="reading__body">' +
          "<div>" +
            '<p class="temp">' + esc(round1(weather.temperature_2m)) +
              '<span class="temp__unit">°C</span></p>' +
            '<p class="condition">' + glyph(group) +
              "<span>" + esc(weather.condition) + "</span></p>" +
          "</div>" +

          '<dl class="metrics">' +
            '<div class="metric"><dt>Feels like</dt><dd>' +
              esc(round1(weather.apparent_temperature)) + "<span>°C</span></dd></div>" +
            '<div class="metric"><dt>Humidity</dt><dd>' +
              esc(weather.relative_humidity_2m) + "<span>%</span></dd></div>" +
            '<div class="metric"><dt>Wind</dt><dd>' +
              esc(round1(weather.wind_speed_10m)) + "<span>km/h</span></dd></div>" +
          "</dl>" +
        "</div>" +

        '<section class="delta">' +
          '<div class="delta__head">' +
            '<h4 class="delta__title">Air vs. feels-like</h4>' +
            '<p class="delta__verdict">' +
              deltaVerdict(weather.temperature_2m, weather.apparent_temperature) +
            "</p>" +
          "</div>" +

          '<div class="delta__scale">' +
            '<span class="delta__marker delta__marker--actual" style="--pos:' + actualPos + '%">' +
              '<span class="delta__flag">Air <b>' +
                esc(round1(weather.temperature_2m)) + "°</b></span>" +
              '<span class="delta__dot"></span>' +
            "</span>" +
            '<span class="delta__marker delta__marker--feels" style="--pos:' + feelsPos + '%">' +
              '<span class="delta__dot"></span>' +
              '<span class="delta__flag">Feels <b>' +
                esc(round1(weather.apparent_temperature)) + "°</b></span>" +
            "</span>" +
          "</div>" +

          '<div class="delta__axis"><span>0°C</span><span>25°C</span><span>50°C</span></div>' +
        "</section>" +

        '<section class="summary">' +
          '<h4 class="summary__title">In plain language</h4>' +
          '<p class="summary__text">' + esc(data.explanation) + "</p>" +
        "</section>" +

        '<p class="reading__foot">' + esc(coords(data.latitude, data.longitude)) + "</p>" +
      "</article>";
  }

  /* ---------- Request ---------- */

  function setLoading(isLoading) {
    button.disabled = isLoading;
    button.setAttribute("data-loading", String(isLoading));
    buttonLabel.textContent = isLoading ? "Reading…" : "Get weather";
    stage.setAttribute("aria-busy", String(isLoading));
  }

  function search(city) {
    var trimmed = String(city || "").trim();

    /* Caught here rather than round-tripping to the 422, so the
       correction is immediate. */
    if (!trimmed) {
      renderError(422, { detail: "Enter a city name to search." });
      input.focus();
      return;
    }

    if (inFlight) {
      inFlight.abort();
    }

    var controller = new AbortController();
    inFlight = controller;

    setLoading(true);
    renderLoading();

    fetch("/weather?city=" + encodeURIComponent(trimmed), {
      headers: { Accept: "application/json" },
      signal: controller.signal
    })
      .then(function (response) {
        return response
          .json()
          .catch(function () { return null; })
          .then(function (payload) {
            return { status: response.status, ok: response.ok, payload: payload };
          });
      })
      .then(function (result) {
        if (controller.signal.aborted) {
          return;
        }

        if (result.ok && result.payload) {
          renderReading(result.payload);
        } else {
          renderError(result.status, result.payload);
        }
      })
      .catch(function () {
        if (!controller.signal.aborted) {
          renderError(0, null);
        }
      })
      .then(function () {
        if (inFlight === controller) {
          inFlight = null;
          setLoading(false);
        }
      });
  }

  /* ---------- Wiring ---------- */

  /* submit covers both the button and Enter in the text field. */
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    search(input.value);
  });

  document.querySelectorAll(".chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      input.value = chip.getAttribute("data-city");
      search(input.value);
    });
  });

  renderEmpty();
})();
