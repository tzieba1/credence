from decimal import Decimal

import pytest

from credence import prompts
from credence.pricing import PRICES, Usage, cost_usd


def test_opus_and_haiku_are_priced() -> None:
    assert {"claude-opus-5-5", "claude-haiku-5-5"} <= set(PRICES)


def test_cost_uses_all_four_token_kinds() -> None:
    usage = Usage(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
    )
    assert cost_usd("claude-opus-5-5", usage) == Decimal("29.20")
    assert cost_usd("claude-haiku-5-5", usage) == Decimal("0.735")


def test_unknown_model_is_an_error_not_a_zero() -> None:
    with pytest.raises(KeyError):
        cost_usd("claude-made-up-9", Usage.none())


def test_prompt_v1_loads() -> None:
    text = prompts.load("v1")
    assert "null" in text and "ISO 8601" in text
    assert prompts.available() == ["v1"]


def test_unknown_prompt_version_is_an_error() -> None:
    with pytest.raises(ValueError, match="unknown prompt version"):
        prompts.load("v99")
