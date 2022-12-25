from . import create_bot_user, page_status, role


def run():
    """
    Run create page statuses, create roles, and create bot user
    """
    page_status.run()
    role.run()
    create_bot_user.run()

    return True
