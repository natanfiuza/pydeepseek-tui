from pydeepseek_tui.providers.pricing import calculate_cost


class TestPricing:
    def test_known_model_deepseek(self):
        cost = calculate_cost("deepseek", "deepseek-v4-pro", 1000, 500)
        # (1000/1M)*2 + (500/1M)*8 = 0.002 + 0.004 = 0.006
        assert cost == 0.006

    def test_known_model_openai(self):
        cost = calculate_cost("openai", "gpt-4o", 2000, 1000)
        # (2000/1M)*2.5 + (1000/1M)*10 = 0.005 + 0.01 = 0.015
        assert cost == 0.015

    def test_known_model_anthropic(self):
        cost = calculate_cost("anthropic", "claude-sonnet-4-6", 1000000, 500000)
        # (1M/1M)*3 + (500k/1M)*15 = 3.0 + 7.5 = 10.5
        assert cost == 10.5

    def test_unknown_provider_returns_zero(self):
        cost = calculate_cost("unknown", "deepseek-v4-pro", 1000, 500)
        assert cost == 0.0

    def test_unknown_model_returns_zero(self):
        cost = calculate_cost("deepseek", "nonexistent-model", 1000, 500)
        assert cost == 0.0

    def test_zero_tokens_returns_zero(self):
        cost = calculate_cost("deepseek", "deepseek-v4-pro", 0, 0)
        assert cost == 0.0

    def test_large_token_count(self):
        cost = calculate_cost("deepseek", "deepseek-v4-pro", 10000000, 5000000)
        # 10M input + 5M output
        assert cost > 0
