# Itinerary JSON schema

The `generate.py` script consumes a single JSON object with this structure.

## Top level

| Field       | Type   | Required | Description |
|-------------|--------|----------|-------------|
| `trip_name` | string | no       | Display title. Overridden by `--title` if passed. |
| `currency`  | string | no       | Currency code/symbol shown next to costs. Default `"$"`. |
| `days`      | array  | **yes**  | Ordered list of day objects. |

## Day object

| Field    | Type   | Required | Description |
|----------|--------|----------|-------------|
| `date`   | string | no       | ISO date `YYYY-MM-DD`. Shown if present. |
| `label`  | string | no       | Heading for the day. Defaults to `Day N`. |
| `stops`  | array  | **yes**  | Ordered list of stop objects. |

## Stop object

| Field      | Type   | Required | Description |
|------------|--------|----------|-------------|
| `name`     | string | **yes**  | Name of the place/activity. |
| `lat`      | number | no       | Latitude. Required together with `lon` to map the stop. |
| `lon`      | number | no       | Longitude. |
| `time`     | string | no       | Time of day, e.g. `"09:00"`. |
| `notes`    | string | no       | Free-text notes shown under the stop. |
| `cost`     | number | no       | Cost for this stop, in `currency`. Default `0`. |
| `category` | string | no       | One of `sightseeing`, `food`, `transport`, `lodging`, `activity`, `other`. Drives the color/icon. Default `other`. |

## Validation rules

- `days` must be a non-empty array.
- Each day's `stops` must be an array (may be empty).
- Each stop must have a non-empty `name`.
- `lat`/`lon`, if present, must both be numbers; a stop with only one is treated
  as having no coordinates.
- `cost`, if present, must be a number.
