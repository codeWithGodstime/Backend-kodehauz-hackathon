import enum
import random


# Base class to allow enums easily serialize to json.
class BaseEnum(enum.Enum):

    def _get_value(self, **kwargs) -> str:
        return self.value

    @classmethod
    def random(cls):
        """
        Return a random enum value from the subclass.
        """
        return random.choice(list(cls))
