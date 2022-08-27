from ambuda.views.proofing import page


def test_get_image_filesystem_path(flask_app):
    with flask_app.app_context():
        path = page._get_image_filesystem_path("project", "1")
    assert path.match("**/project/pages/1.jpg")


def test_edit__unauth(client):
    r = client.get("/proofing/test-project/1/")
    assert "Since you are not logged in" in r.text


def test_edit__auth(rama_client):
    r = rama_client.get("/proofing/test-project/1/")
    assert "Publish changes" in r.text


def test_edit__bad_project(client):
    r = client.get("/proofing/unknown/1/")
    assert r.status_code == 404


def test_edit__bad_page(client):
    r = client.get("/proofing/test-project/unknown/")
    assert r.status_code == 404


def test_history(client):
    r = client.get("/proofing/test-project/1/history")
    assert "History:" in r.text


def test_history__bad_project(client):
    r = client.get("/proofing/unknown/1/history")
    assert r.status_code == 404


def test_history__bad_page(client):
    r = client.get("/proofing/test-project/unknown/history")
    assert r.status_code == 404


def test_revision(client):
    r = client.get("/proofing/test-project/1/revision/1")
    assert "Revision:" in r.text


def test_revision__bad_project(client):
    r = client.get("/proofing/unknown/1/revision/1")
    assert r.status_code == 404


def test_revision__bad_page(client):
    r = client.get("/proofing/test-project/unknown/revision/1")
    assert r.status_code == 404


def test_revision__bad_revision(client):
    r = client.get("/proofing/test-project/1/revision/4000")
    assert r.status_code == 404


def test_revision__bad_revision_non_numeric(client):
    r = client.get("/proofing/test-project/1/revision/unknown")
    assert r.status_code == 404


def test_split_graphemes():
    split = page._split_graphemes("उत्क्रामन्तं")
    assert split == ["उ", "त्", "क्", "रा", "म", "न्", "तं"]
    assert split[0:2] == "उत्"


def test_create_markup():
    markup = page._create_markup("ins", "test")
    assert markup == ("<ins>", "test", "</ins>")

    markup = page._create_markup("del", "\n")
    assert markup == ('<del class="block">', "\n", "</del>")


def test_revision_diff():
    diff = page._revision_diff("वापि", "वापिं")
    assert diff == "वा<del>पि</del><ins>पिं</ins>"

    diff = page._revision_diff("पिहित", "पिहितः")
    assert diff == "पिहि<del>त</del><ins>तः</ins>"

    diff = page._revision_diff("नमस्ते", "नम॑स्ते")
    assert diff == "न<del>म</del><ins>म॑</ins>स्ते"

    diff = page._revision_diff("वापि", "वापि\n")
    assert diff == 'वापि<ins class="block">\n</ins>'

    diff = page._revision_diff("\r\nवापि", "वापि\r\n")
    assert diff == '<del class="block">\r\n</del>वापि<ins class="block">\r\n</ins>'
