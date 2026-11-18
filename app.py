"""METAR-only test page for the FENNEC weather station (fennecweather.com/current)."""
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
import streamlit as st

WEATHER_URL = "https://fennecweather.com/current"
STATION_ID = "FNNC"            # label for the METAR line; change to your field's identifier
TIMEZONE = "America/Chicago"
REFRESH_SECONDS = 60

st.set_page_config(page_title="METAR test", layout="wide")
st.markdown("""
<style>
.metar { font-family:"DejaVu Sans Mono",Consolas,monospace; background:#1f3a5f; color:#fff;
         text-align:center; padding:1.2rem; font-size:2rem; letter-spacing:.04em; }
.note  { color:#888; text-align:center; margin-top:.5rem; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner=False)
def load_weather():
    r = requests.get(WEATHER_URL, timeout=15)
    r.raise_for_status()
    return r.json()["data"][0]


def num(row, *keys):
    """First numeric value found under any of the given field names."""
    for k in keys:
        v = row.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _r(x):
    return int(math.floor(x + 0.5))          # round half up, as METAR does


def _temp(c):
    v = _r(c)
    return ("M" if v < 0 else "") + f"{abs(v):02d}"


def metar_text(row):
    """Unofficial METAR-style line. Visibility, sky condition and present weather
    are not measured by the station, so they are left out."""
    ts = row.get("ts")
    if not isinstance(ts, (int, float)):
        return None
    temp_f = num(row, "temp", "temp_last")
    hum = num(row, "hum", "hum_last")
    dew_f = num(row, "dew_point")
    speed = num(row, "wind_speed_last", "wind_speed_avg_last_10_min", "wind_speed")
    wdir = num(row, "wind_dir_last", "wind_dir")
    gust = num(row, "wind_speed_hi_last_10_min", "wind_gust")
    bar = num(row, "bar_sea_level", "bar_absolute", "bar")

    parts = [STATION_ID, datetime.fromtimestamp(ts, timezone.utc).strftime("%d%H%MZ"), "AUTO"]

    if speed is not None:
        kt = _r(speed * 0.868976)                      # mph -> knots
        if kt == 0:
            wind = "00000KT"
        else:
            d = "VRB" if wdir is None else f"{(_r(wdir / 10) * 10) % 360 or 360:03d}"
            wind = f"{d}{kt:02d}"
            if gust is not None:
                gk = _r(gust * 0.868976)
                if gk - kt >= 10:                      # gust only reported when 10+ kt above speed
                    wind += f"G{gk:02d}"
            wind += "KT"
        parts.append(wind)

    if temp_f is not None:
        tc = (temp_f - 32) * 5 / 9
        dc = None
        if dew_f is not None:
            dc = (dew_f - 32) * 5 / 9
        elif hum:
            g = math.log(hum / 100) + 17.62 * tc / (243.12 + tc)
            dc = 243.12 * g / (17.62 - g)
        parts.append(f"{_temp(tc)}/{_temp(dc) if dc is not None else ''}")

    if bar is not None:
        parts.append(f"A{_r(bar * 100):04d}")

    parts.append("RMK VIS/SKY NOT AVBL")
    return " ".join(parts)


@st.fragment(run_every=REFRESH_SECONDS)
def page():
    try:
        row = load_weather()
    except Exception as e:
        st.error(f"Could not read {WEATHER_URL}: {e}")
        return

    metar = metar_text(row)
    if metar:
        st.markdown(f'<div class="metar">{metar}</div>', unsafe_allow_html=True)
    else:
        st.warning("The data has no 'ts' (timestamp) field, so no METAR could be built.")

    ts = row.get("ts")
    if isinstance(ts, (int, float)):
        when = datetime.fromtimestamp(ts, ZoneInfo(TIMEZONE))
        age = (datetime.now(ZoneInfo(TIMEZONE)) - when).total_seconds() / 60
        st.markdown(f'<div class="note">Observation time: {when.strftime("%b %-d, %-I:%M %p")} '
                    f'({age:.0f} min ago)</div>', unsafe_allow_html=True)

    # Which fields the METAR needs, and whether they were found in the data
    needed = {"temperature": ("temp", "temp_last"), "humidity": ("hum", "hum_last"),
              "dew point (optional)": ("dew_point",),
              "wind speed": ("wind_speed_last", "wind_speed_avg_last_10_min", "wind_speed"),
              "wind direction": ("wind_dir_last", "wind_dir"),
              "gust": ("wind_speed_hi_last_10_min", "wind_gust"),
              "pressure": ("bar_sea_level", "bar_absolute", "bar")}
    st.subheader("Field check")
    for label, keys in needed.items():
        found = [k for k in keys if isinstance(row.get(k), (int, float))]
        st.write(("\u2705 " if found else "\u274c ") + f"**{label}**: "
                 + (f"`{found[0]}` = {row[found[0]]}" if found else f"not found (looked for {', '.join(keys)})"))

    with st.expander("Raw data from the weather station", expanded=False):
        st.json(row)


page()
