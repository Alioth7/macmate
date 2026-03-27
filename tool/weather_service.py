"""
Weather service – auto-location via CoreLocation + wttr.in free API.

Falls back gracefully when CoreLocation is unavailable (e.g. no PyObjC
or no location permission).
"""

import json
import subprocess
from typing import Dict, Optional, Tuple

import requests

from core.tools import registry


class WeatherService:
    """Provide current weather data using system location + wttr.in."""

    WTTR_URL = "https://wttr.in/{query}?format=j1&lang=zh"
    TIMEOUT = 8

    def __init__(self, default_city: str = ""):
        self._default_city = default_city
        registry.bind_instance(self)

    # ------------------------------------------------------------------
    # Registered tool
    # ------------------------------------------------------------------
    @registry.register(
        "get_current_weather",
        "Get current weather. Args: city(str optional, e.g. 'Wuhan'). "
        "If city is empty, auto-detect location via macOS CoreLocation.",
    )
    def get_current_weather_tool(self, city: str = "") -> str:
        city = (city or "").strip()
        if not city:
            city = self._auto_locate_city()
        if not city:
            city = self._default_city or "Wuhan"

        data = self._fetch_weather(city)
        if "error" in data:
            return json.dumps(data, ensure_ascii=False)

        return json.dumps(data, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Quick summary for System Prompt injection (non-blocking)
    # ------------------------------------------------------------------
    def get_weather_summary(self) -> Optional[str]:
        """Return a one-line weather summary or None on failure."""
        try:
            city = self._auto_locate_city() or self._default_city or ""
            if not city:
                return None
            data = self._fetch_weather(city)
            if "error" in data:
                return None
            return (
                f"{data.get('city', city)} | "
                f"{data.get('description', '?')} "
                f"{data.get('temp_c', '?')}°C "
                f"(体感 {data.get('feels_like_c', '?')}°C) "
                f"湿度 {data.get('humidity', '?')}%"
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _fetch_weather(self, query: str) -> Dict:
        try:
            url = self.WTTR_URL.format(query=query)
            resp = requests.get(url, timeout=self.TIMEOUT)
            resp.raise_for_status()
            raw = resp.json()

            current = raw.get("current_condition", [{}])[0]
            area = raw.get("nearest_area", [{}])[0]

            city_name = ""
            area_names = area.get("areaName", [])
            if area_names:
                city_name = area_names[0].get("value", query)

            desc_zh = ""
            lang_zh = current.get("lang_zh", [])
            if lang_zh:
                desc_zh = lang_zh[0].get("value", "")
            if not desc_zh:
                desc_list = current.get("weatherDesc", [])
                desc_zh = desc_list[0].get("value", "") if desc_list else ""

            return {
                "city": city_name or query,
                "temp_c": current.get("temp_C", ""),
                "feels_like_c": current.get("FeelsLikeC", ""),
                "humidity": current.get("humidity", ""),
                "description": desc_zh,
                "wind_speed_kmh": current.get("windspeedKmph", ""),
                "wind_dir": current.get("winddir16Point", ""),
                "observation_time": current.get("observation_time", ""),
            }
        except requests.RequestException as exc:
            return {"error": f"network error: {exc}"}
        except Exception as exc:
            return {"error": f"parse error: {exc}"}

    @staticmethod
    def _auto_locate_city() -> str:
        """Try CoreLocation (PyObjC) to get lat/lon, then reverse to city name."""
        # Attempt 1: CoreLocation via PyObjC
        try:
            import CoreLocation  # type: ignore
            manager = CoreLocation.CLLocationManager.alloc().init()
            location = manager.location()
            if location is not None:
                lat = location.coordinate().latitude
                lon = location.coordinate().longitude
                if lat != 0.0 or lon != 0.0:
                    return f"{lat},{lon}"
        except Exception:
            pass

        # Attempt 2: Parse from macOS `locale` or network-based rough location
        try:
            r = subprocess.run(
                ["defaults", "read", ".GlobalPreferences", "AppleLocale"],
                capture_output=True, text=True, timeout=2, check=False,
            )
            locale_str = (r.stdout or "").strip()  # e.g. "zh_CN"
            # Use locale region as city hint
            if "_CN" in locale_str:
                return "Wuhan"  # default for Chinese locale
            elif "_US" in locale_str:
                return "San Francisco"
        except Exception:
            pass

        return ""
