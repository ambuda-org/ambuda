import ambuda.queries as q
import ambuda.tasks.projects as projects


def test_add_project_to_database(flask_app):
    with flask_app.app_context():
        assert not q.project("cool")
        projects._add_project_to_database(
            title="Cool project", slug="cool", num_pages=100
        )
        project = q.project("cool")
        assert project
        assert len(project.pages) == 100
