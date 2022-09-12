def test_index(client):
    resp = client.get("/about/")
    assert "<h1>About</h1>" in resp.text


def test_mission(client):
    resp = client.get("/about/mission")
    assert "<h1>Mission</h1>" in resp.text


def test_values(client):
    resp = client.get("/about/values")
    assert "<h1>Values</h1>" in resp.text


def test_people(client):
    resp = client.get("/about/people")
    assert "<h1>People</h1>" in resp.text


def test_code_and_data(client):
    resp = client.get("/about/code-and-data")
    assert "<h1>Code and Data</h1>" in resp.text


def test_name(client):
    resp = client.get("/about/our-name")
    assert "<h1>Our Name</h1>" in resp.text


def test_contact(client):
    resp = client.get("/about/contact")
    assert "<h1>Contact</h1>" in resp.text


def test_terms(client):
    resp = client.get("/about/terms")
    assert "<h1>Terms of Use</h1>" in resp.text


def test_privacy(client):
    resp = client.get("/about/privacy-policy")
    assert "<h1>Privacy Policy</h1>" in resp.text
