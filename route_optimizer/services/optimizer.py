from __future__ import annotations

from django.conf import settings

from route_optimizer.services.fuel_optimizer import FuelStopOptimizer
from route_optimizer.services.openrouteservice import OpenRouteServiceClient


class RouteOptimizationService:
    def __init__(self) -> None:
        self.ors_client = OpenRouteServiceClient()
        self.fuel_optimizer = FuelStopOptimizer(self.ors_client)

    def optimize(self, start_location: str, end_location: str) -> dict:
        start = self.ors_client.geocode(start_location)
        end = self.ors_client.geocode(end_location)
        route = self.ors_client.driving_route(start, end)
        fuel_stops = self.fuel_optimizer.select_stops(
            route_geometry=route.geometry,
            total_distance_miles=route.distance_miles,
        )
        total_cost = self.fuel_optimizer.estimate_trip_cost(route.distance_miles, fuel_stops)

        return {
            "start_location": {
                "query": start_location,
                "latitude": round(start.latitude, 6),
                "longitude": round(start.longitude, 6),
            },
            "end_location": {
                "query": end_location,
                "latitude": round(end.latitude, 6),
                "longitude": round(end.longitude, 6),
            },
            "route": {
                "distance_miles": round(route.distance_miles, 2),
                "duration_minutes": round(route.duration_minutes, 2),
                "bbox": route.bbox,
                "geometry": [
                    [round(point.longitude, 6), round(point.latitude, 6)]
                    for point in route.geometry
                ],
            },
            "vehicle": {
                "max_range_miles": settings.VEHICLE_MAX_RANGE_MILES,
                "mpg": settings.VEHICLE_MPG,
                "gallons_required": round(route.distance_miles / settings.VEHICLE_MPG, 2),
            },
            "fuel_stops": [
                {
                    "station_id": stop.station.opis_id,
                    "name": stop.station.name,
                    "address": stop.station.address,
                    "city": stop.station.city,
                    "state": stop.station.state,
                    "latitude": round(stop.location.latitude, 6),
                    "longitude": round(stop.location.longitude, 6),
                    "route_mile": round(stop.route_mile, 2),
                    "detour_miles": round(stop.detour_miles, 2),
                    "price_per_gallon": round(stop.station.price_per_gallon, 3),
                    "gallons_to_buy": stop.gallons_to_buy,
                    "estimated_cost": stop.estimated_cost,
                }
                for stop in fuel_stops
            ],
            "estimated_total_fuel_cost": total_cost,
            "metadata": {
                "routing_provider": "OpenRouteService",
                "external_api_usage": (
                    "Cold request uses start geocode, end geocode, and one route request. "
                    "Trips requiring fuel stops also reverse-geocode target stop areas and may geocode "
                    "a bounded set of candidate stations; all provider results are cached."
                ),
                "fuel_station_strategy": (
                    "Preload CSV once, sample refuel points before the 500-mile range is reached, "
                    "geocode a small price-sorted candidate set, and choose the first station within "
                    "the configured route radius."
                ),
            },
        }
