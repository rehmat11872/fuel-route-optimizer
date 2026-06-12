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
    "start_location": {
        "query": "Los Angeles, CA",
        "latitude": 34.05513,
        "longitude": -118.25703
    },
    "end_location": {
        "query": "Dallas, TX",
        "latitude": 32.736212,
        "longitude": -96.784359
    },
    "route": {
        "distance_miles": 1443.93,
        "duration_minutes": 1326.15,
        "bbox": [
            -118.266787,
            31.035543,
            -96.78439,
            34.087306
        ],
        "geometry": [
            [
                -118.25702,
                34.05513
            ],
            [
                -118.25732,
                34.0548
            ],
            [
                -118.25868,
                34.05316
            ],
            [
                -118.25959,
                34.05233
            ],
            [
                -96.78891,
                32.73895
            ],
            [
                -96.78826,
                32.73846
            ],
            [
                -96.78797,
                32.73819
            ],
            [
                -96.78777,
                32.73796
            ],
            [
                -96.78722,
                32.73718
            ],
            [
                -96.78696,
                32.73674
            ],
            [
                -96.78659,
                32.73619
            ],
            [
                -96.78607,
                32.73525
            ],
            [
                -96.78549,
                32.73552
            ],
            [
                -96.78439,
                32.73606
            ],
            [
                -96.78445,
                32.73614
            ]
        ]
    },
    "vehicle": {
        "max_range_miles": 500.0,
        "mpg": 10.0,
        "gallons_required": 144.39
    },
    "fuel_stops": [
        {
            "station_id": "71030",
            "name": "QUIKTRIP #1469",
            "address": "I-10, EXIT 248 & SR-77",
            "city": "Marana",
            "state": "AZ",
            "latitude": 32.423447,
            "longitude": -111.165674,
            "route_mile": 460.0,
            "detour_miles": 9.25,
            "price_per_gallon": 3.062,
            "gallons_to_buy": 50.0,
            "estimated_cost": 153.12
        },
        {
            "station_id": "69633",
            "name": "ONE9 EXPRESS FUEL",
            "address": "I-10, EXIT 42 & FM-1110",
            "city": "Clint",
            "state": "TX",
            "latitude": 31.60512,
            "longitude": -106.10248,
            "route_mile": 920.0,
            "detour_miles": 80.49,
            "price_per_gallon": 2.802,
            "gallons_to_buy": 50.0,
            "estimated_cost": 140.12
        }
    ],
    "estimated_total_fuel_cost": 423.41,
    "metadata": {
        "routing_provider": "OpenRouteService",
        "external_api_usage": "Cold request uses start geocode, end geocode, and one route request. Trips requiring fuel stops also reverse-geocode target stop areas and may geocode a bounded set of candidate stations; all provider results are cached.",
        "fuel_station_strategy": "Preload CSV once, sample refuel points before the 500-mile range is reached, geocode a small price-sorted candidate set, and choose the first station within the configured route radius."
    }
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
