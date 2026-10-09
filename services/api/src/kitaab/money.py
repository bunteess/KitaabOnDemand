"""Money is stored as integer paisa (1 rupee = 100 paisa)."""


def format_pkr(paisa: int) -> str:
    """Format paisa for display: 125000 -> 'Rs. 1,250', 125050 -> 'Rs. 1,250.50'."""
    sign = "-" if paisa < 0 else ""
    rupees, remainder = divmod(abs(paisa), 100)
    text = f"{rupees:,}"
    if remainder:
        text += f".{remainder:02d}"
    return f"{sign}Rs. {text}"
