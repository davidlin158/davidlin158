---
name: travel-plan-viz
description: Turn a travel itinerary into a self-contained, interactive HTML visualization (day-by-day timeline, map of stops, and budget summary). Use when the user wants to visualize, render, or build a webpage/dashboard for a trip, vacation, or travel plan from a description, list of stops, or a JSON/YAML itinerary.
---

# Travel Plan Visualizer

Generate a single, self-contained HTML file that visualizes a travel itinerary:
a day-by-day timeline, an interactive map of the stops, and a budget summary.
The output has no external build step and no runtime dependencies beyond a CDN
map library, so it opens directly in any browser.

## Workflow

1. **Collect the itinerary.** Gather the trip into structured data. If the user
   gave free-form text ("3 days in Tokyo, then 2 in Kyoto…"), turn it into the
   itinerary JSON shape below yourself before generating. Ask only for details
   that materially change the output and that you cannot reasonably infer
   (e.g. travel dates if the user wants a dated timeline). Sensible defaults are
   fine for everything else.

2. **Write the itinerary to a JSON file**, e.g. `itinerary.json`, following the
   schema in `references/schema.md`.

3. **Generate the visualization** by running:

   ```bash
   python3 scripts/generate.py itinerary.json -o trip.html --title "My Trip"
   ```

4. **Surface the result.** Tell the user where `trip.html` is. If the session
   supports sending files, send it so they can open it.

## Itinerary data shape

Minimal example — see `references/schema.md` for the full schema:

```json
{
  "trip_name": "Japan Spring Trip",
  "currency": "USD",
  "days": [
    {
      "date": "2026-04-01",
      "label": "Day 1 — Tokyo",
      "stops": [
        {
          "name": "Senso-ji Temple",
          "lat": 35.7148,
          "lon": 139.7967,
          "time": "09:00",
          "notes": "Arrive early to beat crowds",
          "cost": 0,
          "category": "sightseeing"
        }
      ]
    }
  ]
}
```

## Notes

- `lat`/`lon` are optional per stop. Stops without coordinates still appear on
  the timeline; only geolocated stops are drawn on the map.
- If no stop has coordinates, the map section is omitted automatically.
- `cost` is summed per day and across the trip for the budget panel.
- The script validates the JSON and prints a clear error if a required field is
  missing, so fix the data and re-run rather than editing the HTML by hand.
