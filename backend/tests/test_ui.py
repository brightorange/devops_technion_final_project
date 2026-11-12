def test_ui_is_served(client):
    response = client.get("/ui")
    assert response.status_code == 200
    assert b"Northwind Supply" in response.data


def test_ui_is_not_at_root(client):
    # The UI lives at /ui so the ingress can route it without a "/" prefix
    # rule, which would also expose /health/*.
    assert client.get("/").status_code == 404
