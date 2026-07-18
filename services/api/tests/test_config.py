from conftest import TestCtx
from fastapi.testclient import TestClient

from api.app import create_app


def test_config_known_site(tctx: TestCtx) -> None:
    client = TestClient(create_app(tctx))
    response = client.get("/config/demo")
    assert response.status_code == 200
    assert response.json() == {
        "sampling_rate": 1.0,
        "experiments": [
            {
                "id": "checkout-cta-color",
                "variants": ["control", "green"],
                "traffic": 0.5,
            },
            {
                "id": "hero-image-lazyload",
                "variants": ["control", "eager"],
                "traffic": 0.2,
            },
        ],
    }


def test_config_unknown_site_is_404(tctx: TestCtx) -> None:
    client = TestClient(create_app(tctx))
    assert client.get("/config/nope").status_code == 404
