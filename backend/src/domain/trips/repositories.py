from __future__ import annotations

from typing import Optional, Protocol

from src.domain.trips.models import TripRecord


class TripRepository(Protocol):
    def save(self, trip: TripRecord) -> TripRecord: ...

    def get(self, trip_id: str) -> Optional[TripRecord]: ...

    def list_recent(self, limit: int = 20) -> list[TripRecord]: ...

    def list_review_queue(self, limit: int = 20) -> list[TripRecord]: ...
