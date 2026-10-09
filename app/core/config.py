from msflib.account.config import AccountSettings
from msflib.ai_core.config import AICoreSettings
from msflib.auth.config import AuthSettings
from msflib.core.config import CoreSettings, SettingsBase
from msflib.payments.config import PaymentsSettings
from msflib.tenancy import TenancySettings
from msflib.workspaces.config import WorkspaceSettings


class AppSettings(
    AICoreSettings,
    PaymentsSettings,
    WorkspaceSettings,
    TenancySettings,
    AccountSettings,
    AuthSettings,
    CoreSettings,
    SettingsBase,
):
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    REDIS_HOST: str | None = None
    REDIS_PORT: str | None = None
    REDIS_PASSWORD: str | None = None

    INVALID_JWT_EXPIRE: int | None = 3600
    EMAIL_TEMPLATES_DIR: str = "./app/email-templates/build"
    PASSWORD_RESET_PATH: str = "/password-reset"

    # File storage
    STORAGE_METHOD: str | None = "file"
    STORAGE_PATH: str | None = "./uploads"

    # Server-Sent Event Stream settings.
    STREAM_RETRY_TIMEOUT: int = 15000  # millisecond
    STREAM_DELAY: int = 1  # second

    # Paid plan amount in the currency subunit (kobo for NGN). Paystack secret and
    # callback URL come from PaymentsSettings (PAYSTACK_SECRET_KEY, PAYMENT_CALLBACK_URL).
    SOCIALCHEF_BILLING_AMOUNT: int | None = None
    SOCIALCHEF_BILLING_CURRENCY: str = "NGN"
    SOCIALCHEF_SUBSCRIPTION_PERIOD_DAYS: int = 30

    # Meta app secret and hub verify token for WhatsApp Cloud API and
    # Messenger/Instagram webhooks. Empty values fail closed.
    # LLM provider, model, and key come from AICoreSettings
    # (AICORE_LLM_PROVIDER, AICORE_LLM_MODEL, AICORE_LLM_API_KEY).
    META_APP_SECRET: str = ""
    META_WEBHOOK_VERIFY_TOKEN: str = ""


settings = AppSettings()
