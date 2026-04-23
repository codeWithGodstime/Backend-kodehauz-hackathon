from msflib.core.config import CoreSettings, SettingsBase
from msflib.auth.config import AuthSettings
from msflib.account.config import AccountSettings


class Settings(AccountSettings, AuthSettings, CoreSettings, SettingsBase):
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    REDIS_HOST: Optional[str] = None
    REDIS_PORT: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None

    INVALID_JWT_EXPIRE: Optional[int] = 3600
    EMAIL_TEMPLATES_DIR: str = "./app/email-templates/build"
    PASSWORD_RESET_PATH: str = "/password-reset"
    INVALID_JWT_EXPIRE: Optional[int] = 3600

    # File storage
    STORAGE_METHOD: Optional[str] = "file"
    STORAGE_PATH: Optional[str] = "./uploads"

    # Server-Sent Event Stream settings.
    STREAM_RETRY_TIMEOUT = 15000  # milisecond
    STREAM_DELAY = 1  # second


settings = Settings()
