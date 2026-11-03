"""What a call costs, from the usage the API reports and a price table kept here."""

from dataclasses import dataclass
from decimal import Decimal

from anthropic.types import Usage as ApiUsage


@dataclass(frozen=True)
class Usage:
    """Token counts for one call. Cache counts are zero when the API reports none."""

    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    @classmethod
    def from_api(cls, usage: ApiUsage) -> "Usage":
        return cls(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_input_tokens=usage.cache_read_input_tokens or 0,
            cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
        )

    @classmethod
    def none(cls) -> "Usage":
        return cls(input_tokens=0, output_tokens=0)


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input: Decimal
    output: Decimal
    cache_read: Decimal
    cache_write: Decimal


# Claude API list prices, November 2026. Haiku 5.5 prices are for prompts of
# 100K tokens or fewer, which every document this service accepts stays under.
PRICES: dict[str, Price] = {
    "claude-opus-5-5": Price(
        input=Decimal("4.00"),
        output=Decimal("20.00"),
        cache_read=Decimal("0.20"),
        cache_write=Decimal("5.00"),
    ),
    "claude-haiku-5-5": Price(
        input=Decimal("0.10"),
        output=Decimal("0.50"),
        cache_read=Decimal("0.01"),
        cache_write=Decimal("0.125"),
    ),
}

_MILLION = Decimal(1_000_000)


def cost_usd(model: str, usage: Usage) -> Decimal:
    """The cost of one call. Raises KeyError for a model the table does not price."""
    price = PRICES[model]
    total = (
        usage.input_tokens * price.input
        + usage.output_tokens * price.output
        + usage.cache_read_input_tokens * price.cache_read
        + usage.cache_creation_input_tokens * price.cache_write
    )
    return total / _MILLION
