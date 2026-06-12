from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from django.conf import settings
from django.core.cache import cache

from route_optimizer.exceptions import FuelStationError
from route_optimizer.services.cache_keys import stable_cache_key
from route_optimizer.services.fuel_data import FuelStation, load_fuel_stations
from route_optimizer.services.geo import Coordinate, haversine_miles, interpolate_at_distance
from route_optimizer.services.openrouteservice import OpenRouteServiceClient


@dataclass(frozen=True)
class FuelStop:
    station: FuelStation
    location: Coordinate
    route_mile: float
    detour_miles: float
    gallons_to_buy: float
    estimated_cost: float


class FuelStopOptimizer:
    def __init__(self, ors_client: OpenRouteServiceClient) -> None:
        self.ors_client = ors_client
        self.max_range_miles = settings.VEHICLE_MAX_RANGE_MILES
        self.mpg = settings.VEHICLE_MPG
        self.search_radius_miles = settings.FUEL_SEARCH_RADIUS_MILES
        self.candidate_count = settings.FUEL_CANDIDATES_PER_STOP
        self.max_geocode_candidates = settings.FUEL_MAX_GEOCODE_CANDIDATES_PER_STOP

    def select_stops(self, route_geometry: list[Coordinate], total_distance_miles: float) -> list[FuelStop]:
        if total_distance_miles <= self.max_range_miles:
            return []

        stops_needed = ceil(total_distance_miles / self.max_range_miles) - 1
        stops: list[FuelStop] = []
        selected_station_ids: set[str] = set()

        for stop_number in range(1, stops_needed + 1):
            target_mile = min(stop_number * self.max_range_miles * 0.92, total_distance_miles - 1)
            target_point = interpolate_at_distance(route_geometry, target_mile)
            station, location, detour = self._best_station_near(target_point, selected_station_ids)
            selected_station_ids.add(station.opis_id or station.full_address)

            gallons = self.max_range_miles / self.mpg
            stops.append(
                FuelStop(
                    station=station,
                    location=location,
                    route_mile=target_mile,
                    detour_miles=detour,
                    gallons_to_buy=round(gallons, 2),
                    estimated_cost=round(gallons * station.price_per_gallon, 2),
                )
            )

        return stops

    def estimate_trip_cost(self, total_distance_miles: float, stops: list[FuelStop]) -> float:
        gallons_required = total_distance_miles / self.mpg
        if stops:
            weighted_price = sum(stop.station.price_per_gallon for stop in stops) / len(stops)
        else:
            stations = load_fuel_stations()
            weighted_price = min(station.price_per_gallon for station in stations)
        return round(gallons_required * weighted_price, 2)

    def _best_station_near(
        self,
        target_point: Coordinate,
        already_selected: set[str],
    ) -> tuple[FuelStation, Coordinate, float]:
        target_place = self.ors_client.reverse_geocode_place(target_point)
        stations = self._ranked_candidates(
            already_selected,
            target_state=target_place.state,
            target_city=target_place.city,
        )
        closest: tuple[FuelStation, Coordinate, float] | None = None

        for station in stations:
            location = self._station_coordinate(station)
            if location is None:
                continue

            detour = haversine_miles(target_point, location)
            if closest is None or detour < closest[2]:
                closest = (station, location, detour)
            if detour <= self.search_radius_miles:
                return station, location, detour

        if closest is not None:
            return closest

        raise FuelStationError(
            "No fuel station could be geocoded from the provided fuel price dataset.",
            code="no_station_near_route",
        )

    def _ranked_candidates(
        self,
        already_selected: set[str],
        target_state: str | None,
        target_city: str | None,
    ) -> list[FuelStation]:
        sorted_stations = sorted(load_fuel_stations(), key=lambda item: item.price_per_gallon)
        city_candidates = [
            station
            for station in sorted_stations
            if target_city
            and station.city.upper() == target_city
            and (station.opis_id or station.full_address) not in already_selected
        ]
        state_candidates = [
            station
            for station in sorted_stations
            if target_state
            and station.state == target_state
            and (station.opis_id or station.full_address) not in already_selected
            and station not in city_candidates
        ]
        fallback_candidates = [
            station
            for station in sorted_stations
            if (station.opis_id or station.full_address) not in already_selected
            and station not in city_candidates
            and station not in state_candidates
        ]
        candidates = city_candidates + state_candidates + fallback_candidates
        return candidates[: max(self.candidate_count, self.max_geocode_candidates)]

    def _station_coordinate(self, station: FuelStation) -> Coordinate | None:
        cache_key = stable_cache_key("station-coord", f"{station.opis_id}:{station.full_address.lower()}")
        cached = cache.get(cache_key)
        if cached:
            return Coordinate(**cached)

        coordinate = None
        for query in station.geocode_queries:
            try:
                coordinate = self.ors_client.geocode(query, timeout=6)
                break
            except Exception:
                continue

        if coordinate is None:
            return None

        cache.set(cache_key, coordinate.__dict__, timeout=60 * 60 * 24 * 365)
        return coordinate
