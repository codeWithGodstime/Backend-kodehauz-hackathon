# from msflib.workspaces.eventbus import register_hooks as register_workspace_hooks

# from . import eventbus  # noqa: F401
# from .actions import workspace_action, user_action, account_action


_hooks_registered = False


def bootstrap_module_hooks() -> None:
    global _hooks_registered
    if _hooks_registered:
        return

    # register_workspace_hooks(
    #     workspace_action=workspace_action,
    #     user_action=user_action,
    #     account_action=account_action,
    # )
    _hooks_registered = True
