def test_index(client):
    resp = client.get("/blog/")
    assert resp.status_code == 200
    assert "Sample post" in resp.text


def test_post(client):
    resp = client.get("/blog/p/sample-post")
    assert resp.status_code == 200
    assert "Sample post" in resp.text


def test_create_post(admin_client):
    # Test that the "create post" page loads for admin users.
    resp = admin_client.get("/blog/create")
    assert resp.status_code == 200


def test_edit_post(admin_client):
    resp = admin_client.get("/blog/p/sample-post/edit")
    assert resp.status_code == 200


def test_delete_post(admin_client):
    resp = admin_client.get("/blog/p/sample-post/delete")
    assert resp.status_code == 200


def test_create_post__non_admin(moderator_client):
    # Test that the "create post" page loads fails for non-admin users.
    resp = moderator_client.get("/blog/create")
    assert resp.status_code == 302


def test_edit_post__non_admin(moderator_client):
    resp = moderator_client.get("/blog/p/sample-post/edit")
    assert resp.status_code == 302


def test_delete_post__non_admin(moderator_client):
    resp = moderator_client.get("/blog/p/sample-post/delete")
    assert resp.status_code == 302
