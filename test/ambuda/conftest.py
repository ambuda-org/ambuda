import pytest
from flask_login import FlaskLoginClient
from sqlalchemy.engine import Engine

import ambuda.database as db
from ambuda import create_app
from ambuda.consts import BOT_USERNAME, TEXT_CATEGORIES
from ambuda.queries import get_engine, get_session
from ambuda.seed.lookup import page_status as page_status_seeding
from ambuda.seed.lookup import role as role_seeding


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
    engine = get_engine()
    assert ":memory:" in engine.url

    db.Base.metadata.drop_all(engine)
    db.Base.metadata.create_all(engine)

    # Seed scripts
    role_seeding.run(engine)
    page_status_seeding.run(engine)

    session = get_session()

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

    # Bot
    bot = db.User(username=BOT_USERNAME, email="ambuda-bot@ambuda.org")
    bot.set_password("pass_bod")
    session.add(bot)
    session.flush()

    # Auth
    u_basic = db.User(username="u-basic", email="u_basic@ambuda.org")
    u_basic.set_password("pass_basic")
    session.add(u_basic)
    session.flush()

    # Basic user with only P1 permissions.
    u_p1 = db.User(username="u-p1", email="u-p1@ambuda.org")
    u_p1.set_password("pass_p1")
    session.add(u_p1)
    session.flush()

    # Basic user with P2 permissions.
    u_p2 = db.User(username="u-p2", email="u-p2@ambuda.org")
    u_p2.set_password("pass_p2")
    session.add(u_p2)
    session.flush()

    # Moderator
    moderator = db.User(username="u-moderator", email="u_moderator@ambuda.org")
    moderator.set_password("pass_moderator")
    session.add(moderator)
    session.flush()

    # Admin
    admin = db.User(username="u-admin", email="u_admin@ambuda.org")
    admin.set_password("pass_admin")
    session.add(admin)
    session.flush()

    # Deleted and Banned
    deleted_admin = db.User(username="u-deleted", email="u_deleted@ambuda.org")
    deleted_admin.set_password("pass_deleted")
    deleted_admin.set_is_deleted(True)

    banned = db.User(username="u-banned", email="u_banned@ambuda.org")
    banned.set_password("pass_banned")
    banned.set_is_banned(True)

    session.add(deleted_admin)
    session.add(banned)
    session.flush()

    # Roles
    p1_role = session.query(db.Role).filter_by(name="p1").one()
    p2_role = session.query(db.Role).filter_by(name="p2").one()
    moderator_role = session.query(db.Role).filter_by(name="moderator").one()
    admin_role = session.query(db.Role).filter_by(name="admin").one()

    session.add(p1_role)
    session.add(p2_role)
    session.add(moderator_role)
    session.add(admin_role)
    session.flush()

    u_p1.roles = [p1_role]
    u_p2.roles = [p1_role, p2_role]
    u_basic.roles = [p1_role, p2_role]
    moderator.roles = [p1_role, p2_role, moderator_role]
    admin.roles = [p1_role, p2_role, admin_role]
    deleted_admin.roles = [p1_role, p2_role, admin_role]
    banned.roles = [p1_role]
    session.add(u_p1)
    session.add(u_p2)
    session.add(u_basic)
    session.add(moderator)
    session.add(admin)
    session.add(deleted_admin)
    session.add(banned)
    session.flush()

    # Blog
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

    reviewed_0 = session.query(db.PageStatus).filter_by(name="reviewed-0").one()

    # Add 100 dummy pages.
    for i in range(1, 101):
        page = db.Page(
            project_id=project.id, slug=str(i), order=i, status_id=reviewed_0.id
        )
        session.add(page)
        session.flush()

        revision = db.Revision(
            project_id=project.id,
            page_id=page.id,
            author_id=admin.id,
            status_id=reviewed_0.id,
            content=f"This is page {i} of 100.",
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


@pytest.fixture(scope="session")
def db_engine(flask_app) -> Engine:
    with flask_app.app_context():
        return get_engine()


@pytest.fixture()
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture()
def p1_client(flask_app):
    session = get_session()
    user = session.query(db.User).filter_by(username="u-p1").one()
    return flask_app.test_client(user=user)


@pytest.fixture()
def p2_client(flask_app):
    session = get_session()
    user = session.query(db.User).filter_by(username="u-p2").one()
    return flask_app.test_client(user=user)


@pytest.fixture()
def rama_client(flask_app):
    session = get_session()
    user = session.query(db.User).filter_by(username="u-basic").one()
    return flask_app.test_client(user=user)


@pytest.fixture()
def moderator_client(flask_app):
    session = get_session()
    moderator = session.query(db.User).filter_by(username="u-moderator").one()
    return flask_app.test_client(user=moderator)


@pytest.fixture()
def admin_client(flask_app):
    session = get_session()
    user = session.query(db.User).filter_by(username="u-admin").one()
    return flask_app.test_client(user=user)


@pytest.fixture()
def deleted_client(flask_app):
    session = get_session()
    user = session.query(db.User).filter_by(username="u-deleted").one()
    return flask_app.test_client(user=user)


@pytest.fixture()
def banned_client(flask_app):
    session = get_session()
    user = session.query(db.User).filter_by(username="u-banned").one()
    return flask_app.test_client(user=user)
