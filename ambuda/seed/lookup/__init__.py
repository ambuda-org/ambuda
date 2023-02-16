from . import create_bot_user, page_status, role


def run():
    """
    Run create page statuses, create roles, and create bot user
    """
    try:
        page_status.run()
        role.run()
        create_bot_user.run()
    except Exception as ex:
        raise Exception(
            "Error: Failed to create page statuses, "
            "create roles, and creat bot user."
            f"Error: {ex}"
        )
