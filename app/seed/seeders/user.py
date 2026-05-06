from msflib.seed import BaseSeeder
from msflib.seed.schema import ConfigSchema
from msflib.seed.utils import get_dependency_value
from sqlmodel import Session

from app import models
from app.actions import user_action as ua


class UserSeeder(BaseSeeder):
    def __init__(self, config: ConfigSchema):
        self.config = config
        self.records = config.records if config.records else [ua.random().dict()]

    def seed(self, session: Session, seeds):
        accounts = seeds["accounts"]
        users = []
        update = get_dependency_value(self.config, seeds)
        for account, record in zip(accounts, self.records):
            user = ua.create_random(session, account_id=account.id, **{**record, **update})
            usercreate = ua.random_register(account_id=account.id, **{**record, **update})
            userinfo = models.UserInfo(**{**usercreate.info.dict(), "id": user.id})

            session.add(userinfo)
            if usercreate.type == models.UserType.learner.value:
                student = models.Student(**{**usercreate.student.dict(), "id": user.id})
                session.add(student)

            elif usercreate.type == models.UserType.trainer.value:
                trainer = models.Trainer(**{**usercreate.trainer.dict(), "id": user.id})
                session.add(trainer)

            session.commit()
            session.refresh(user)
            users.append(user)
        seeds.update({self.config.name: users})
