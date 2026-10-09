from typing import Any

from msflib.seed.base import SeederBase
from msflib.seed.schema import ConfigSchema
from sqlmodel import Session

from app.seed.demo import ensure_socialchef_seed


class SocialchefDemoSeeder(SeederBase):
    """Same demo rows as ``app.initial_data``. Safe to run more than once."""

    def __init__(self, config: ConfigSchema) -> None:
        self.config = config

    def seed(self, session: Session, seeds: dict[str, Any]) -> None:
        ensure_socialchef_seed(session)
        seeds.update({self.config.name: True})
