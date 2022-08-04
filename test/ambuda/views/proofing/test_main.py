def test_index(client):
    resp = client.get("/proofing/")
    assert resp.status_code == 200


def test_beginners_guide(client):
    resp = client.get("/proofing/beginners-guide")
    assert "Beginner's guide" in resp.text


def test_complete_guide(client):
    resp = client.get("/proofing/complete-guide")
    assert "Proofing guidelines" in resp.text


def test_recent_changes(client):
    resp = client.get("/proofing/recent-changes")
    assert ">Recent changes<" in resp.text


def test_upload_images__unauth(client):
    resp = client.get("/proofing/create-new-project")
    assert resp.status_code == 302


def test_upload_images__auth(rama_client):
    resp = rama_client.get("/proofing/create-new-project")
    assert resp.status_code == 200
