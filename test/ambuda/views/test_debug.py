def test_style(client):
    r = client.get("/debug/style")
    assert r.status_code == 200
