"""Plan code for the Paystack initialize call.

``process_payment`` builds a ``PaymentCreate`` that has no plan field, so the
gateway subclass reads the code from this context variable.
"""

from contextvars import ContextVar

paystack_plan_code: ContextVar[str | None] = ContextVar("paystack_plan_code", default=None)
