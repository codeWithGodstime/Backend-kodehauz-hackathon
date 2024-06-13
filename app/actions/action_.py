from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    get_args,
    get_origin,
)

from pydantic import BaseModel
from sqlalchemy.sql.elements import BinaryExpression
from sqlmodel import Session, SQLModel, or_, select

ModelType = TypeVar("ModelType", bound=SQLModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class Action(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    # Holds the specific types corresponding to generic types 'ModelType',
    # 'CreateSchemaType' and 'UpdateSchemaType' for specified subclasses.
    _type_args: Optional[Tuple[Type[ModelType], Type[CreateSchemaType], Type[UpdateSchemaType]]] = (
        None
    )

    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """
        Initializes a subclass of `Action`. Identifies `Action` among all base classes
        and saves the specific provided type argument in the `_type_args` class
        attribute.
        """
        super().__init_subclass__(**kwargs)
        for base in cls.__orig_bases__:  # type: ignore[attr-defined]
            origin = get_origin(base)
            if origin is None or not issubclass(origin, Action):
                continue
            type_args = get_args(base)
            # Do not set the attribute for GENERIC subclasses!
            if not isinstance(type_args[0], TypeVar):
                cls._type_args = type_args
                return

    @classmethod
    def get_type_arg(cls) -> Tuple[Type[ModelType], Type[CreateSchemaType], Type[UpdateSchemaType]]:
        if cls._type_args is None:
            raise AttributeError(f"{cls.__name__} is generic; type argument unspecified")
        return cls._type_args

    def get(self, session: Session, id: Any) -> Optional[ModelType]:
        SpecificType = self.__class__.get_type_arg()[0]
        return session.get(SpecificType, id)

    def get_multi(self, session: Session, *, offset: int = 0, limit: int = 100) -> List[ModelType]:
        SpecificType = self.__class__.get_type_arg()[0]
        return session.exec(select(SpecificType).offset(offset).limit(limit)).all()

    def get_multi_by_expressions(
        self, session: Session, *exprs: List[BinaryExpression], offset: int = 0, limit: int = 100
    ) -> List[ModelType]:
        SpecificType = self.__class__.get_type_arg()[0]
        return session.exec(select(SpecificType).where(*exprs).offset(offset).limit(limit)).all()

    def get_multi_by_any(
        self, session: Session, *, offset: int = 0, limit: int = 100, **dict: dict
    ) -> Optional[ModelType]:
        SpecificType = self.__class__.get_type_arg()[0]
        or_list = [
            (SpecificType.__getattribute__(SpecificType, key) == value)
            for key, value in dict.items()
        ]
        return session.exec(
            select(SpecificType).where(or_(*or_list)).offset(offset).limit(limit)
        ).all()

    def get_multi_by_all(
        self, session: Session, *, offset: int = 0, limit: int = 100, **dict: dict
    ) -> Optional[ModelType]:
        SpecificType = self.__class__.get_type_arg()[0]
        and_list = [
            (SpecificType.__getattribute__(SpecificType, key) == value)
            for key, value in dict.items()
        ]
        return session.exec(select(SpecificType).where(*and_list).offset(offset).limit(limit)).all()

    def get_by_any(self, session: Session, **dict: dict) -> Optional[ModelType]:
        SpecificType = self.__class__.get_type_arg()[0]
        or_list = [
            (SpecificType.__getattribute__(SpecificType, key) == value)
            for key, value in dict.items()
        ]
        return session.exec(select(SpecificType).where(or_(*or_list))).first()

    def get_by_all(self, session: Session, **dict: dict) -> Optional[ModelType]:
        SpecificType = self.__class__.get_type_arg()[0]
        and_list = [
            (SpecificType.__getattribute__(SpecificType, key) == value)
            for key, value in dict.items()
        ]
        return session.exec(select(SpecificType).where(*and_list)).first()

    def get_by_expressions(
        self, session: Session, *exprs: List[BinaryExpression]
    ) -> Optional[ModelType]:
        SpecificType = self.__class__.get_type_arg()[0]
        return session.exec(select(SpecificType).where(*exprs)).first()

    def create(
        self,
        session: Session,
        *,
        data: CreateSchemaType,
        update: Optional[Dict[str, Any]] = {},
        decorator: Callable[[ModelType], Any] = None,
    ) -> ModelType:
        SpecificType = self.__class__.get_type_arg()[0]
        model = SpecificType.from_orm(data, update=update)

        # Modify the object model if decorator is provided.
        if decorator is not None:
            decorator(model)

        session.add(model)
        session.commit()
        session.refresh(model)
        return model

    def update(
        self,
        session: Session,
        *,
        model: ModelType,
        data: Optional[UpdateSchemaType] = None,
        update: Optional[Dict[str, Any]] = {},
        decorator: Callable[[ModelType], Any] = None,
    ) -> ModelType:
        update_data = data.dict(exclude_unset=True) if data is not None else {}
        update_data = {**update_data, **update}
        for key, value in update_data.items():
            setattr(model, key, value)

        # Modify the object model if decorator is provided.
        if decorator is not None:
            decorator(model)

        session.add(model)
        session.commit()
        session.refresh(model)
        return model

    def delete(self, session: Session, *, id: int) -> Optional[ModelType]:
        SpecificType = self.__class__.get_type_arg()[0]
        model = session.get(SpecificType, id)
        if model:
            session.delete(model)
            session.commit()
        return model

    def delete_by_any(self, session: Session, **dict: dict) -> Optional[ModelType]:
        SpecificType = self.__class__.get_type_arg()[0]
        or_list = [
            (SpecificType.__getattribute__(SpecificType, key) == value)
            for key, value in dict.items()
        ]
        item = session.exec(select(SpecificType).where(or_(*or_list))).first()
        if item:
            session.delete(item)
            session.commit()
        return item

    def delete_by_all(self, session: Session, **dict: dict) -> Optional[ModelType]:
        SpecificType = self.__class__.get_type_arg()[0]
        and_list = [
            (SpecificType.__getattribute__(SpecificType, key) == value)
            for key, value in dict.items()
        ]
        item = session.exec(select(SpecificType).where(*and_list)).first()
        if item:
            session.delete(item)
            session.commit()
        return item


__classes = {}


def base(
    model_type: Type[ModelType],
    create_type: Type[CreateSchemaType],
    update_type: Type[UpdateSchemaType],
) -> Action:
    """
    Create a dynamic Action subclass (or pull a cached copy) and return an instance.
    """
    key = (model_type.__name__, create_type.__name__, update_type.__name__)
    if key not in __classes.keys():
        clazz = type(
            f"Action{model_type.__name__}",
            (Action,),
            {"_type_args": (model_type, create_type, update_type)},
        )

    else:
        clazz = __classes[key]

    return clazz()
