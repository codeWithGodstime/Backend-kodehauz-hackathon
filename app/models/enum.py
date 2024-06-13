import enum


# Base class to allow enums easily serialize to json.
class BaseEnum(enum.Enum):

    def _get_value(self, **kwargs) -> str:
        return self.value
