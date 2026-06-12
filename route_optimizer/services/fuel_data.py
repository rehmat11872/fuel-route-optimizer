from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from route_optimizer.exceptions import FuelStationError


@dataclass(frozen=True)
class FuelStation:
    opis_id: str
    name: str
    address: str
    city: str
    state: str
    rack_id: str
    price_per_gallon: float

    @property
    def full_address(self) -> str:
        return f"{self.name}, {self.address}, {self.city}, {self.state}, USA"

    @property
    def geocode_queries(self) -> tuple[str, ...]:
        return (
            self.full_address,
            f"{self.address}, {self.city}, {self.state}, USA",
            f"{self.city}, {self.state}, USA",
        )


@lru_cache(maxsize=1)
def load_fuel_stations() -> tuple[FuelStation, ...]:
    csv_path = Path(settings.FUEL_PRICES_CSV_PATH)
    if not csv_path.exists():
        raise FuelStationError(f"Fuel price file not found: {csv_path}", code="fuel_file_missing")

    stations: list[FuelStation] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                price = float(row["Retail Price"])
            except (KeyError, TypeError, ValueError):
                continue

            stations.append(
                FuelStation(
                    opis_id=(row.get("OPIS Truckstop ID") or "").strip(),
                    name=(row.get("Truckstop Name") or "").strip(),
                    address=(row.get("Address") or "").strip(),
                    city=(row.get("City") or "").strip(),
                    state=(row.get("State") or "").strip().upper(),
                    rack_id=(row.get("Rack ID") or "").strip(),
                    price_per_gallon=price,
                )
            )

    if not stations:
        raise FuelStationError("No valid fuel stations were loaded.", code="fuel_file_empty")

    return tuple(stations)


def cheapest_stations(limit: int, states: set[str] | None = None) -> list[FuelStation]:
    stations = load_fuel_stations()
    if states:
        filtered = [station for station in stations if station.state in states]
    else:
        filtered = list(stations)
    return sorted(filtered, key=lambda station: station.price_per_gallon)[:limit]
