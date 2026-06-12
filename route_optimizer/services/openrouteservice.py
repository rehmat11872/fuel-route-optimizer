from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

from route_optimizer.exceptions import RoutingServiceError
from route_optimizer.services.cache_keys import stable_cache_key
from route_optimizer.services.geo import Coordinate


@dataclass(frozen=True)
class RouteResult:
    distance_miles: float
    duration_minutes: float
    geometry: list[Coordinate]
    encoded_polyline: str | None
    bbox: list[float] | None


@dataclass(frozen=True)
class ReverseGeocodeResult:
    state: str | None
    city: str | None


class OpenRouteServiceClient:
    def __init__(self) -> None:
        self.base_url = settings.ORS_BASE_URL.rstrip("/")
        self.api_key = settings.OPENROUTESERVICE_API_KEY
        if not self.api_key:
            raise RoutingServiceError("OPENROUTESERVICE_API_KEY is not configured.")

    def geocode(self, query: str, timeout: int = 20) -> Coordinate:
        cache_key = stable_cache_key("ors-geocode", query.lower().strip())
        cached = cache.get(cache_key)
        if cached:
            return Coordinate(**cached)

        response = self._request(
            "GET",
            "/geocode/search",
            params={
                "text": query,
                "boundary.country": "USA",
                "size": 1,
            },
            timeout=timeout,
        )
        features = response.get("features", [])
        if not features:
            raise RoutingServiceError(f"Could not geocode location: {query}", code="geocode_not_found")

        coordinate = Coordinate.from_ors(features[0]["geometry"]["coordinates"])
        cache.set(cache_key, coordinate.__dict__, timeout=60 * 60 * 24 * 30)
        return coordinate

    def reverse_geocode_place(self, coordinate: Coordinate) -> ReverseGeocodeResult:
        cache_key = stable_cache_key(
            "ors-reverse-place",
            f"{coordinate.latitude:.4f},{coordinate.longitude:.4f}",
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return ReverseGeocodeResult(**cached)

        response = self._request(
            "GET",
            "/geocode/reverse",
            params={
                "point.lon": coordinate.longitude,
                "point.lat": coordinate.latitude,
                "boundary.country": "USA",
                "size": 1,
            },
        )
        features = response.get("features", [])
        state = None
        city = None
        if features:
            properties = features[0].get("properties", {})
            state = (properties.get("region_a") or "").upper()
            city = (
                properties.get("locality")
                or properties.get("localadmin")
                or properties.get("county")
                or ""
            ).upper()

        result = ReverseGeocodeResult(state=state or None, city=city or None)
        cache.set(cache_key, result.__dict__, timeout=60 * 60 * 24 * 30)
        return result

    def driving_route(self, start: Coordinate, end: Coordinate) -> RouteResult:
        cache_key = stable_cache_key(
            "ors-route",
            f"{start.latitude:.5f},{start.longitude:.5f}:{end.latitude:.5f},{end.longitude:.5f}",
        )
        cached = cache.get(cache_key)
        if cached:
            return RouteResult(
                distance_miles=cached["distance_miles"],
                duration_minutes=cached["duration_minutes"],
                geometry=[Coordinate(**point) for point in cached["geometry"]],
                encoded_polyline=cached["encoded_polyline"],
                bbox=cached["bbox"],
            )

        response = self._request(
            "POST",
            "/v2/directions/driving-car",
            json={
                "coordinates": [start.to_ors(), end.to_ors()],
                "instructions": False,
                "geometry_simplify": True,
            },
        )
        routes = response.get("routes", [])
        if not routes:
            raise RoutingServiceError("Routing service returned no route.", code="route_not_found")

        route = routes[0]
        summary = route["summary"]
        encoded_polyline = route.get("geometry")
        geometry = decode_polyline(encoded_polyline) if encoded_polyline else []
        if not geometry:
            raise RoutingServiceError("Routing service returned an empty route geometry.", code="route_geometry_empty")

        result = RouteResult(
            distance_miles=summary["distance"] / 1609.344,
            duration_minutes=summary["duration"] / 60,
            geometry=geometry,
            encoded_polyline=encoded_polyline,
            bbox=route.get("bbox") or response.get("bbox"),
        )
        cache.set(
            cache_key,
            {
                "distance_miles": result.distance_miles,
                "duration_minutes": result.duration_minutes,
                "geometry": [point.__dict__ for point in result.geometry],
                "encoded_polyline": result.encoded_polyline,
                "bbox": result.bbox,
            },
            timeout=60 * 60 * 24,
        )
        return result

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        headers = kwargs.pop("headers", {})
        timeout = kwargs.pop("timeout", 20)
        headers["Authorization"] = self.api_key
        headers["Accept"] = "application/json"
        if method.upper() == "POST":
            headers["Content-Type"] = "application/json"

        try:
            response = requests.request(
                method=method,
                url=f"{self.base_url}{path}",
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise RoutingServiceError(f"Routing service request failed: {exc}") from exc

        if response.status_code >= 400:
            raise RoutingServiceError(
                f"Routing service returned HTTP {response.status_code}.",
                code="routing_http_error",
            )
        return response.json()


def decode_polyline(polyline: str, precision: int = 5) -> list[Coordinate]:
    coordinates: list[Coordinate] = []
    index = 0
    lat = 0
    lng = 0
    factor = 10 ** precision

    while index < len(polyline):
        lat_change, index = _decode_polyline_value(polyline, index)
        lng_change, index = _decode_polyline_value(polyline, index)
        lat += lat_change
        lng += lng_change
        coordinates.append(Coordinate(latitude=lat / factor, longitude=lng / factor))

    return coordinates


def _decode_polyline_value(polyline: str, index: int) -> tuple[int, int]:
    result = 0
    shift = 0

    while True:
        byte = ord(polyline[index]) - 63
        index += 1
        result |= (byte & 0x1F) << shift
        shift += 5
        if byte < 0x20:
            break

    value = ~(result >> 1) if result & 1 else result >> 1
    return value, index
