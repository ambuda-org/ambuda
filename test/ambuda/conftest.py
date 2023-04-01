import pytest
from flask_login import FlaskLoginClient

import ambuda.database as db
from ambuda import create_app
from ambuda.consts import BOT_USERNAME, TEXT_CATEGORIES
from ambuda.models.base import db as flask_sqla
from ambuda.queries import get_session


def _add_dictionaries(session):
    """Add dummy dictionary data."""
    d1 = db.Dictionary(slug="dict-1", title="Test Dictionary 1")
    d2 = db.Dictionary(slug="dict-2", title="Test Dictionary 2")
    session.add_all([d1, d2])
    session.flush()

    e1 = db.DictionaryEntry(dictionary_id=d1.id, key="agni", value="<div>fire</div>")
    e2 = db.DictionaryEntry(dictionary_id=d2.id, key="agni", value="<div>ignis</div>")
    session.add_all([e1, e2])
    session.flush()


def initialize_test_db():
    flask_sqla.drop_all()
    flask_sqla.create_all()

    session = flask_sqla.session

    # Text and parse data
    text = db.Text(slug="pariksha", title="parIkSA")
    session.add(text)
    session.flush()

    # Create stubs for all texts so that texts.index doesn't break
    for _category, slugs in TEXT_CATEGORIES.items():
        for slug in slugs:
            t = db.Text(slug=slug, title=slug)
            session.add(t)
            session.flush()

    section = db.TextSection(text_id=text.id, slug="1", title="adhyAyaH 1")
    session.add(section)
    section2 = db.TextSection(text_id=text.id, slug="2", title="adhyAyaH 2")
    session.add(section2)
    session.flush()

    block = db.TextBlock(
        text_id=text.id, section_id=section.id, slug="1.1", xml="<div>agniH</div>", n=1
    )
    session.add(block)
    session.flush()

    parse = db.BlockParse(
        text_id=text.id, block_id=block.id, data="agniH\tagni\tpos=n,g=m,c=1,n=s"
    )
    session.add(parse)

    _add_dictionaries(session)

    # Bot user
    bot = db.User(username=BOT_USERNAME, email="ambuda-bot@ambuda.org")
    bot.set_password("password")
    session.add(bot)
    session.flush()

    # Basic user
    rama = db.User(username="ramacandra", email="rama@ayodhya.com")
    rama.set_password("maithili")
    session.add(rama)
    session.flush()

    # Moderator
    moderator = db.User(username="u-mod", email="mod@ambuda.org")
    moderator.set_password("secret password")
    session.add(moderator)
    session.flush()

    # Admin
    admin = db.User(username="u-admin", email="admin@ambuda.org")
    admin.set_password("secret password")
    session.add(admin)
    session.flush()

    # Deleted and Banned
    deleted_admin = db.User(username="u-deleted-banned", email="cgm@ambuda.org")
    deleted_admin.set_password("maurya")
    deleted_admin.set_is_deleted(True)

    banned = db.User(username="u-banned", email="alex@ambuda.org")
    banned.set_password("onesicritus")
    banned.set_is_banned(True)

    session.add(deleted_admin)
    session.add(banned)
    session.flush()

    # Roles
    p1_role = db.Role(name=db.SiteRole.P1.value)
    p2_role = db.Role(name=db.SiteRole.P2.value)
    moderator_role = db.Role(name=db.SiteRole.MODERATOR.value)
    admin_role = db.Role(name=db.SiteRole.ADMIN.value)
    session.add(p1_role)
    session.add(p2_role)
    session.add(moderator_role)
    session.add(admin_role)
    session.flush()

    rama.roles = [p1_role, p2_role]
    moderator.roles = [p1_role, p2_role, moderator_role]
    admin.roles = [p1_role, p2_role, admin_role]
    deleted_admin.roles = [p1_role, p2_role, admin_role]
    banned.roles = [p1_role]
    session.add(rama)
    session.add(moderator)
    session.add(admin)
    session.add(deleted_admin)
    session.add(banned)
    session.flush()

    # Blog posts
    post = db.BlogPost(
        title="Sample post",
        slug="sample-post",
        content="This is a sample post.",
        author_id=admin.id,
    )
    session.add(post)
    session.commit()

    # Proofing
    board = db.Board(title="board")
    session.add(board)
    session.flush()

    thread = db.Thread(title="Some thread", author_id=admin.id)
    post = db.Post(content="This is my post.", author_id=admin.id)
    post.board = board
    post.thread = thread
    board.threads = [thread]

    project = db.Project(slug="test-project", title="Test Project", board_id=board.id)
    session.add(project)
    session.flush()

    page_status = db.PageStatus(name="reviewed-0")
    session.add(page_status)
    session.flush()

    page = db.Page(project_id=project.id, slug="1", order=1, status_id=page_status.id)
    session.add(page)
    session.flush()

    revision = db.Revision(
        project_id=project.id,
        page_id=page.id,
        author_id=admin.id,
        status_id=page_status.id,
        content="Foo",
    )
    session.add(revision)

    session.commit()


@pytest.fixture(scope="session")
def flask_app():
    app = create_app("testing")
    app.config.update({"TESTING": True})
    app.test_client_class = FlaskLoginClient

    with app.app_context():
        initialize_test_db()

    yield app


@pytest.fixture()
def client(flask_app):
    with flask_app.app_context():
        yield flask_app.test_client()


@pytest.fixture()
def rama_client(flask_app):
    with flask_app.app_context():
        session = get_session()
        user = session.query(db.User).filter_by(username="ramacandra").first()
        return flask_app.test_client(user=user)


@pytest.fixture()
def moderator_client(flask_app):
    with flask_app.app_context():
        session = get_session()
        moderator = session.query(db.User).filter_by(username="u-mod").first()
        return flask_app.test_client(user=moderator)


@pytest.fixture()
def admin_client(flask_app):
    with flask_app.app_context():
        session = get_session()
        user = session.query(db.User).filter_by(username="u-admin").first()
        return flask_app.test_client(user=user)


@pytest.fixture()
def deleted_client(flask_app):
    with flask_app.app_context():
        session = get_session()
        user = session.query(db.User).filter_by(username="u-deleted-banned").first()
        return flask_app.test_client(user=user)


@pytest.fixture()
def banned_client(flask_app):
    with flask_app.app_context():
        session = get_session()
        user = session.query(db.User).filter_by(username="u-banned").first()
        return flask_app.test_client(user=user)
