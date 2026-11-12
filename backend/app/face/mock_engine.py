from __future__ import annotations

from app.face.base import Candidate, EnrollResult, MatchResult


class MockFaceEngine:
    """Chỉ giữ hợp đồng M4; tuyệt đối không tạo kết quả nhận diện giả."""

    name = "mock"
    version = "1.0"
    is_ready = False

    def assess_enrollment(self, image: bytes) -> EnrollResult:
        return EnrollResult(ok=True, quality_score=None, embedding=None, reason=None)

    def identify(self, image: bytes, candidates: list[Candidate]) -> list[MatchResult]:
        return []

    def embed_stored_image(self, image: bytes) -> EnrollResult:
        return EnrollResult(ok=False, quality_score=None, embedding=None, reason="engine_not_ready")
