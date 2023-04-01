def test_index(client):
    resp = client.get("/blog/")
    assert resp.status_code == 200
    assert "Sample post" in resp.text


def test_post(client):
    resp = client.get("/blog/p/sample-post")
    assert resp.status_code == 200
    assert "Sample post" in resp.text


def test_post__missing(client):
    resp = client.get("/blog/p/missing")
    assert resp.status_code == 404


def test_create_post(admin_client):
    # Test that the "create post" page loads for admin users.
    resp = admin_client.get("/blog/create")
    assert resp.status_code == 200

    resp = admin_client.post(
        "/blog/create", data={"title": "Title", "content": "Content"}
    )
    assert resp.status_code == 302


def test_edit_post(admin_client):
    resp = admin_client.post(
        "/blog/create", data={"title": "some post", "content": "some content"}
    )
    assert resp.status_code == 302

    resp = admin_client.get("/blog/p/some-post/edit")
    assert resp.status_code == 200

    resp = admin_client.post(
        "/blog/p/some-post/edit", data={"title": "Title", "content": "Content"}
    )
    assert resp.status_code == 302


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
