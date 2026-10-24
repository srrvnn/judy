ORIGIN = "https://my-app.lovable.app"


def test_simple_request_gets_cors_header(client):
    response = client.get("/v1/plugs", headers={"Origin": ORIGIN})
    assert response.headers["access-control-allow-origin"] == "*"


def test_preflight_allows_patch_and_json(client):
    response = client.options(
        "/v1/plugs/1",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type,last-event-id",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "PATCH" in response.headers["access-control-allow-methods"]
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "content-type" in allowed and "last-event-id" in allowed
