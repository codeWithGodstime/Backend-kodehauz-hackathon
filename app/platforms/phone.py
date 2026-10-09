"""Normalize phone strings the way WhatsApp Cloud API sends them."""


def normalize_phone(value: str | None) -> str | None:
    """Digits only. ``+234 801`` and ``234801`` match the same business line."""
    if value is None:
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits or None
