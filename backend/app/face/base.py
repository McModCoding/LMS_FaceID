from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass
class FaceBox:
    x: float
    y: float
    w: float
    h: float
    det_score: float


@dataclass
class EnrollResult:
    ok: bool
    quality_score: float | None
    embedding: bytes | None
    reason: str | None


@dataclass
class Candidate:
    student_id: int
    embeddings: list[bytes]


@dataclass
class MatchResult:
    box: FaceBox
    student_id: int | None
    status: Literal["matched", "unknown", "ambiguous", "low_quality"]
    score: float | None
    margin: float | None


class FaceEngine(Protocol):
    name: str
    version: str
    is_ready: bool

    def assess_enrollment(self, image: bytes) -> EnrollResult: ...
    def identify(self, image: bytes, candidates: list[Candidate]) -> list[MatchResult]: ...
    def embed_stored_image(self, image: bytes) -> EnrollResult: ...
