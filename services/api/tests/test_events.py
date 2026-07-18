from conftest import EPOCH, TestCtx
from fastapi.testclient import TestClient

from api.app import create_app

EVENT = {
    "site_id": "demo",
    "page_url": "/checkout",
    "lcp_ms": 2410.5,
    "timestamp": 1784415300000,
    "session_id": "s-abc123",
}


def _queue_rows(tctx: TestCtx) -> list[tuple[object, ...]]:
    return list(
        tctx.db.queue.execute(
            "SELECT site_id, page_url, lcp_ms, ts_ms, session_id, received_at_ms"
            " FROM queue ORDER BY id"
        )
    )


def test_post_event_enqueues_typed_row(tctx: TestCtx) -> None:
    client = TestClient(create_app(tctx))
    response = client.post("/events", json=EVENT)
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    # received_at_ms comes from ctx.clock (frozen at EPOCH), not the wall.
    assert _queue_rows(tctx) == [
        (
            "demo",
            "/checkout",
            2410.5,
            1784415300000,
            "s-abc123",
            int(EPOCH.timestamp() * 1000),
        )
    ]


def test_post_event_rejects_invalid_payload(tctx: TestCtx) -> None:
    # "Infinity" coerces to inf and passes ge=0 unless allow_inf_nan=False —
    # one Inf row would poison every p75 aggregate downstream.
    client = TestClient(create_app(tctx))
    missing_field = {k: v for k, v in EVENT.items() if k != "site_id"}
    negative_lcp = {**EVENT, "lcp_ms": -1}
    infinite_lcp = {**EVENT, "lcp_ms": "Infinity"}
    assert client.post("/events", json=missing_field).status_code == 422
    assert client.post("/events", json=negative_lcp).status_code == 422
    assert client.post("/events", json=infinite_lcp).status_code == 422
    assert _queue_rows(tctx) == []
