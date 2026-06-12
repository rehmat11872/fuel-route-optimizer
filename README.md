# Fuel Route Optimizer API

Django REST Framework API that accepts a USA start and finish location, retrieves a driving route from OpenRouteService, selects cost-effective fuel stops from the provided station price CSV, and returns route geometry, stop details, and estimated fuel cost.

## Tech Stack

- Python 3.13+
- Django 6.x
- Django REST Framework
- OpenRouteService for geocoding and driving directions
- SQLite for local development

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Create `.env` from `.env.example` and set `OPENROUTESERVICE_API_KEY`.

The included `.env` is only for local assessment convenience. Rotate the key before using it outside this exercise.

## API

### Health Check

```http
GET http://127.0.0.1:8000/api/health/
```

### Optimize Route

```http
POST http://127.0.0.1:8000/api/optimize-route/
Content-Type: application/json

{
  "start_location": "Los Angeles, CA",
  "end_location": "Dallas, TX"
}
```

Example `curl`:

```bash
curl -X POST http://127.0.0.1:8000/api/optimize-route/ \
  -H "Content-Type: application/json" \
  -d '{"start_location":"Los Angeles, CA","end_location":"Dallas, TX"}'
```

Postman setup:

- Method: `POST`
- URL: `http://127.0.0.1:8000/api/optimize-route/`
- Headers: `Content-Type: application/json`
- Body: raw JSON with `start_location` and `end_location`

## Algorithm

1. Geocode the start and end locations within the USA.
2. Request one driving route from OpenRouteService using the geocoded coordinates.
3. Use the route geometry and total distance in miles from the routing response.
4. Assume the vehicle starts full, gets 10 MPG, and can drive 500 miles on a full tank.
5. For trips over 500 miles, place target refuel points at about 92% of each tank range to leave safety margin.
6. Load the fuel CSV once via an in-process LRU cache.
7. Reverse-geocode each refuel target to city/state, sort matching stations by `Retail Price`, geocode a bounded candidate set, and cache station coordinates.
8. Pick the first station within the configured radius from that price-sorted candidate list.
9. Estimate trip fuel cost as `total_distance / 10 * selected_average_price`.

## Response Shape

```json
{
  "start_location": {"query": "Los Angeles, CA", "latitude": 34.05, "longitude": -118.24},
  "end_location": {"query": "Dallas, TX", "latitude": 32.77, "longitude": -96.79},
  "route": {
    "distance_miles": 1435.2,
    "duration_minutes": 1280.5,
    "bbox": [-118.4, 32.1, -96.7, 35.2],
    "geometry": [[-118.24, 34.05], [-117.9, 34.1]]
  },
  "vehicle": {
    "max_range_miles": 500,
    "mpg": 10,
    "gallons_required": 143.52
  },
  "fuel_stops": [
    {
      "station_id": "20",
      "name": "PILOT TRAVEL CENTER #1243",
      "address": "I-8, EXIT 119 & SR-85",
      "city": "Gila Bend",
      "state": "AZ",
      "latitude": 32.94,
      "longitude": -112.72,
      "route_mile": 460,
      "detour_miles": 4.8,
      "price_per_gallon": 3.899,
      "gallons_to_buy": 50,
      "estimated_cost": 194.95
    }
  ],
  "estimated_total_fuel_cost": 559.66
}
```

## Error Handling

- `400`: invalid request body or impossible fuel station match
- `502`: routing/geocoding provider failure
- `500`: unexpected server error

All custom errors return:

```json
{"detail": "Message", "code": "machine_readable_code"}
```

## Performance Notes

- The fuel CSV is loaded once with `functools.lru_cache`, avoiding repeated disk reads.
- OpenRouteService geocoding and route responses are cached through Django cache.
- Station geocoding is cached for a year.
- For production scale, replace `LocMemCache` with Redis.
- Add latitude/longitude columns to the fuel station dataset or pre-geocode it offline to remove station geocoding calls during requests. This is the biggest performance win because the provided CSV has no coordinates.
- Store stations in PostGIS and use a spatial index for precise corridor searches.
- Cache common route requests by normalized origin/destination.
