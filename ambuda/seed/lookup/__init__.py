
from . import page_status, role, create_bot_user

def run():
    """
    Run create page statuses, create roles, and create bot user
    """
    page_status.run()
    role.run()
    create_bot_user.run()

    return True