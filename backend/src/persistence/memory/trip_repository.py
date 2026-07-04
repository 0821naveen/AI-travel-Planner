from __future__ import annotations

from threading import Lock
from typing import Dict, Optional

from src.domain.trips.models import TripRecord
from src.domain.trips.repositories import TripRepository


class InMemoryTripRepository(TripRepository):
    def __init__(self) -> None:
        self._records: Dict[str, TripRecord] = {}
        self._lock = Lock()

    def save(self, trip: TripRecord) -> TripRecord:
        with self._lock:
            self._records[trip.trip_id] = trip
        return trip

    def get(self, trip_id: str) -> Optional[TripRecord]:
        with self._lock:
            return self._records.get(trip_id)

    def list_recent(self, limit: int = 20) -> list[TripRecord]:
        with self._lock:
            records = sorted(self._records.values(), key=lambda item: item.updated_at, reverse=True)
            return records[:limit]

    def list_review_queue(self, limit: int = 20) -> list[TripRecord]:
        with self._lock:
            records = [
                item for item in self._records.values() if item.human_approval.status.value in {"pending", "rejected"}
            ]
            records.sort(key=lambda item: item.updated_at, reverse=True)
            return records[:limit]
