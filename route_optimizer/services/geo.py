from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Iterable


EARTH_RADIUS_MILES = 3958.7613


@dataclass(frozen=True)
class Coordinate:
    latitude: float
    longitude: float

    @classmethod
    def from_ors(cls, pair: list[float]) -> "Coordinate":
        longitude, latitude = pair
        return cls(latitude=latitude, longitude=longitude)

    def to_ors(self) -> list[float]:
        return [self.longitude, self.latitude]


def haversine_miles(a: Coordinate, b: Coordinate) -> float:
    lat1, lon1, lat2, lon2 = map(radians, [a.latitude, a.longitude, b.latitude, b.longitude])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * asin(sqrt(h))


def cumulative_distances(points: list[Coordinate]) -> list[float]:
    if not points:
        return []

    distances = [0.0]
    total = 0.0
    for previous, current in zip(points, points[1:]):
        total += haversine_miles(previous, current)
        distances.append(total)
    return distances


def interpolate_at_distance(points: list[Coordinate], target_miles: float) -> Coordinate:
    if not points:
        raise ValueError("Cannot interpolate an empty route.")

    distances = cumulative_distances(points)
    if target_miles <= 0:
        return points[0]
    if target_miles >= distances[-1]:
        return points[-1]

    for index in range(1, len(distances)):
        if distances[index] >= target_miles:
            start = points[index - 1]
            end = points[index]
            segment = distances[index] - distances[index - 1]
            if segment == 0:
                return end
            ratio = (target_miles - distances[index - 1]) / segment
            return Coordinate(
                latitude=start.latitude + (end.latitude - start.latitude) * ratio,
                longitude=start.longitude + (end.longitude - start.longitude) * ratio,
            )
    return points[-1]


def route_states_from_bbox(points: Iterable[Coordinate]) -> set[str]:
    """Coarse state hinting is intentionally delegated to station state filtering elsewhere."""
    return set()
