PRICING: dict[str, dict[str, dict[str, float]]] = {
    "deepseek": {
        "deepseek-v4-pro": {"input_per_1m": 2.00, "output_per_1m": 8.00},
        "deepseek-v4": {"input_per_1m": 1.00, "output_per_1m": 4.00},
    },
    "openai": {
        "gpt-4o": {"input_per_1m": 2.50, "output_per_1m": 10.00},
    },
    "anthropic": {
        "claude-sonnet-4-6": {"input_per_1m": 3.00, "output_per_1m": 15.00},
    },
}


def calculate_cost(
    provider: str, model: str, input_tokens: int, output_tokens: int
) -> float:
    model_prices = PRICING.get(provider, {}).get(model)
    if not model_prices:
        return 0.0
    input_cost = (input_tokens / 1_000_000) * model_prices.get("input_per_1m", 0)
    output_cost = (output_tokens / 1_000_000) * model_prices.get("output_per_1m", 0)
    return round(input_cost + output_cost, 8)
