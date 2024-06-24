# Provides CRUD operations in a reusable set of classes.

from .action_ import Action, base
from .action_account import account
from .action_profile import profile


# from app.models import Tomato, TomatoCreate, TomatoUpdate

# Add CRUD handler for a specific type that inherits from base implementation.
# tomato = base(Tomato, TomatoCreate, TomatoUpdate)
