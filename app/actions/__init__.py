# Provides CRUD operations in a reusable set of classes.

from ._action import ModelAction, action
from .account import account
from .profile import profile


# from app.models import Tomato, TomatoCreate, TomatoUpdate

# Add CRUD handler for a specific type that inherits from base implementation.
# tomato = action(Tomato, TomatoCreate, TomatoUpdate)



# For a new basic set of CRUD operations you could just do

# from faker import Faker
# from app.actions import action
# from app.models.item import Item, ItemCreate, ItemUpdate
#
# faker = Faker()
# item_actions = action(
#   Item,
#   ItemCreate,
#   ItemUpdate,
#   lambda self, **dict: ItemCreate(
#       name=dict.get("name", faker.name()),
#       description=dict.get("description", faker.paragraph()),
#       ...,
#   ),
# )


# Elsewhere in the codebase

# from app.actions import item_actions as ia
#
# ia.create(...)
# ia.update(...)
# ia.random()   # To generate random data
# ia.create_random()    # To generate random data and save it to the database
