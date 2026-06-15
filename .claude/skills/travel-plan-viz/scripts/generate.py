#!/usr/bin/env python3
"""Generate a self-contained HTML visualization from a travel itinerary JSON.

Usage:
    python3 generate.py itinerary.json -o trip.html --title "My Trip"

See ../references/schema.md for the input schema.
"""
import argparse
import html
import json
import sys

CATEGORY_COLORS = {
    "sightseeing": "#2563eb",
    "food": "#ea580c",
    "transport": "#0891b2",
    "lodging": "#7c3aed",
    "activity": "#16a34a",
    "other": "#64748b",
}
CATEGORY_ICONS = {
    "sightseeing": "📷",
    "food": "🍴",
    "transport": "🚆",
    "lodging": "🛏️",
    "activity": "🎯",
    "other": "📍",
}


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def validate(data):
    if not isinstance(data, dict):
        fail("top-level JSON must be an object")
    days = data.get("days")
    if not isinstance(days, list) or not days:
        fail("'days' must be a non-empty array")
    for di, day in enumerate(days):
        if not isinstance(day, dict):
            fail(f"day {di} must be an object")
        stops = day.get("stops")
        if not isinstance(stops, list):
            fail(f"day {di} 'stops' must be an array")
        for si, stop in enumerate(stops):
            if not isinstance(stop, dict):
                fail(f"day {di} stop {si} must be an object")
            name = stop.get("name")
            if not isinstance(name, str) or not name.strip():
                fail(f"day {di} stop {si} requires a non-empty 'name'")
            cost = stop.get("cost", 0)
            if not isinstance(cost, (int, float)):
                fail(f"day {di} stop '{name}' has non-numeric 'cost'")


def stop_coords(stop):
    lat, lon = stop.get("lat"), stop.get("lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return lat, lon
    return None


def esc(value):
    return html.escape(str(value))


def build_timeline(days, currency):
    out = []
    for i, day in enumerate(days):
        label = day.get("label") or f"Day {i + 1}"
        date = day.get("date")
        header = esc(label)
        if date:
            header += f' <span class="date">{esc(date)}</span>'
        day_cost = sum(s.get("cost", 0) or 0 for s in day.get("stops", []))
        cards = []
        for stop in day.get("stops", []):
            cat = stop.get("category", "other")
            if cat not in CATEGORY_COLORS:
                cat = "other"
            color = CATEGORY_COLORS[cat]
            icon = CATEGORY_ICONS[cat]
            time = f'<span class="time">{esc(stop["time"])}</span>' if stop.get("time") else ""
            notes = f'<p class="notes">{esc(stop["notes"])}</p>' if stop.get("notes") else ""
            cost = stop.get("cost", 0) or 0
            cost_html = f'<span class="cost">{esc(currency)}{cost:g}</span>' if cost else ""
            cards.append(
                f'<li class="stop" style="border-left-color:{color}">'
                f'<div class="stop-head"><span class="icon">{icon}</span>'
                f'<span class="stop-name">{esc(stop["name"])}</span>{time}{cost_html}</div>'
                f'{notes}</li>'
            )
        cost_badge = (
            f'<span class="day-cost">{esc(currency)}{day_cost:g}</span>' if day_cost else ""
        )
        out.append(
            f'<section class="day"><h2>{header}{cost_badge}</h2>'
            f'<ul class="stops">{"".join(cards)}</ul></section>'
        )
    return "\n".join(out)


def collect_markers(days):
    markers = []
    for i, day in enumerate(days):
        for stop in day.get("stops", []):
            coords = stop_coords(stop)
            if coords:
                cat = stop.get("category", "other")
                if cat not in CATEGORY_COLORS:
                    cat = "other"
                markers.append(
                    {
                        "lat": coords[0],
                        "lon": coords[1],
                        "name": stop["name"],
                        "day": day.get("label") or f"Day {i + 1}",
                        "color": CATEGORY_COLORS[cat],
                    }
                )
    return markers


MAP_SECTION = """
  <section class="map-wrap">
    <h2>Map</h2>
    <div id="map"></div>
  </section>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const markers = __MARKERS__;
    const map = L.map('map');
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors', maxZoom: 19
    }).addTo(map);
    const latlngs = [];
    markers.forEach(m => {
      latlngs.push([m.lat, m.lon]);
      L.circleMarker([m.lat, m.lon], {
        radius: 8, color: '#fff', weight: 2, fillColor: m.color, fillOpacity: 1
      }).addTo(map).bindPopup('<b>' + m.name + '</b><br>' + m.day);
    });
    if (latlngs.length > 1) {
      L.polyline(latlngs, {color: '#94a3b8', weight: 2, dashArray: '6'}).addTo(map);
      map.fitBounds(latlngs, {padding: [40, 40]});
    } else if (latlngs.length === 1) {
      map.setView(latlngs[0], 13);
    } else {
      map.setView([0, 0], 2);
    }
  </script>
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>__TITLE__</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         margin: 0; background: #f8fafc; color: #0f172a; }
  header.hero { background: linear-gradient(135deg,#1e3a8a,#2563eb); color:#fff;
         padding: 2rem 1.5rem; }
  header.hero h1 { margin: 0 0 .25rem; font-size: 1.8rem; }
  header.hero p { margin: 0; opacity: .85; }
  main { max-width: 960px; margin: 0 auto; padding: 1.5rem; }
  .summary { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
  .stat { background:#fff; border:1px solid #e2e8f0; border-radius:12px;
          padding: .9rem 1.2rem; flex:1; min-width: 130px; }
  .stat .num { font-size: 1.5rem; font-weight: 700; }
  .stat .lbl { font-size: .8rem; color:#64748b; text-transform: uppercase;
               letter-spacing: .04em; }
  .day { background:#fff; border:1px solid #e2e8f0; border-radius:12px;
         padding: 1rem 1.2rem; margin-bottom: 1.2rem; }
  .day h2 { margin: 0 0 .8rem; font-size: 1.15rem; display:flex;
            align-items:center; gap:.6rem; }
  .day h2 .date { font-size:.85rem; color:#64748b; font-weight:400; }
  .day-cost { margin-left:auto; font-size:.9rem; background:#eff6ff;
              color:#1d4ed8; padding:.15rem .55rem; border-radius:999px; }
  ul.stops { list-style:none; margin:0; padding:0; }
  .stop { border-left: 4px solid #64748b; padding:.5rem .8rem; margin:.4rem 0;
          background:#f8fafc; border-radius:0 8px 8px 0; }
  .stop-head { display:flex; align-items:center; gap:.5rem; }
  .stop-name { font-weight:600; }
  .stop .time { font-size:.82rem; color:#64748b; }
  .stop .cost { margin-left:auto; font-size:.82rem; color:#0f766e; font-weight:600; }
  .stop .notes { margin:.35rem 0 0 1.7rem; font-size:.88rem; color:#475569; }
  .map-wrap { background:#fff; border:1px solid #e2e8f0; border-radius:12px;
              padding:1rem 1.2rem; margin-bottom:1.2rem; }
  .map-wrap h2 { margin:0 0 .8rem; font-size:1.15rem; }
  #map { height: 380px; border-radius:8px; }
  footer { text-align:center; color:#94a3b8; font-size:.8rem; padding:1.5rem; }
  @media (prefers-color-scheme: dark) {
    body { background:#0f172a; color:#e2e8f0; }
    .stat,.day,.map-wrap { background:#1e293b; border-color:#334155; }
    .stop { background:#0f172a; }
    .stat .lbl,.day h2 .date,.stop .time,.stop .notes { color:#94a3b8; }
    .day-cost { background:#1e3a8a; color:#bfdbfe; }
  }
</style>
</head>
<body>
<header class="hero">
  <h1>__TITLE__</h1>
  <p>__SUBTITLE__</p>
</header>
<main>
  <div class="summary">
    <div class="stat"><div class="num">__NDAYS__</div><div class="lbl">Days</div></div>
    <div class="stat"><div class="num">__NSTOPS__</div><div class="lbl">Stops</div></div>
    <div class="stat"><div class="num">__TOTALCOST__</div><div class="lbl">Est. Cost</div></div>
  </div>
__MAP__
  __TIMELINE__
</main>
<footer>Generated by the travel-plan-viz skill</footer>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="Visualize a travel itinerary as HTML.")
    ap.add_argument("itinerary", help="Path to itinerary JSON file")
    ap.add_argument("-o", "--output", default="trip.html", help="Output HTML path")
    ap.add_argument("--title", help="Override the trip title")
    args = ap.parse_args()

    try:
        with open(args.itinerary, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        fail(f"itinerary file not found: {args.itinerary}")
    except json.JSONDecodeError as e:
        fail(f"invalid JSON: {e}")

    validate(data)

    days = data["days"]
    currency = data.get("currency", "$")
    title = args.title or data.get("trip_name") or "Travel Plan"

    n_days = len(days)
    n_stops = sum(len(d.get("stops", [])) for d in days)
    total_cost = sum(
        (s.get("cost", 0) or 0) for d in days for s in d.get("stops", [])
    )

    markers = collect_markers(days)
    if markers:
        map_section = MAP_SECTION.replace("__MARKERS__", json.dumps(markers))
    else:
        map_section = ""

    dates = [d["date"] for d in days if d.get("date")]
    subtitle = f"{dates[0]} – {dates[-1]}" if len(dates) >= 2 else (dates[0] if dates else f"{n_days}-day itinerary")

    total_cost_str = f"{esc(currency)}{total_cost:g}" if total_cost else "—"

    page = (
        PAGE.replace("__TITLE__", esc(title))
        .replace("__SUBTITLE__", esc(subtitle))
        .replace("__NDAYS__", str(n_days))
        .replace("__NSTOPS__", str(n_stops))
        .replace("__TOTALCOST__", total_cost_str)
        .replace("__MAP__", map_section)
        .replace("__TIMELINE__", build_timeline(days, currency))
    )

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(page)

    print(f"Wrote {args.output} — {n_days} days, {n_stops} stops, {len(markers)} mapped.")


if __name__ == "__main__":
    main()
