def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


class MathService:
    """Math operations service."""

    def compute(self, x: int, y: int) -> int:
        res = add(x, y)
        return res
