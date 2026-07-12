from __future__ import annotations

import unittest

from backend.app.strategies.contracts import compile_strategy


STRATEGY = {
    "engine": "rules",
    "entry": [{"field": "return_5", "operator": ">", "value": 0}],
    "exit": [{"field": "return_1", "operator": "<", "value": -0.5}],
    "risk": {"max_position_pct": 10, "stop_loss_pct": 2, "take_profit_pct": 4},
}


class StrategyContractTests(unittest.TestCase):
    def test_contract_is_deterministic_and_blocks_execution_runtimes(self) -> None:
        first = compile_strategy(STRATEGY)
        second = compile_strategy({**STRATEGY, "risk": dict(STRATEGY["risk"])})

        self.assertEqual(first["strategy_hash"], second["strategy_hash"])
        self.assertEqual(first["required_fields"], ["return_1", "return_5"])
        self.assertTrue(first["capabilities"]["backtest"])
        self.assertFalse(first["capabilities"]["paper"])
        self.assertFalse(first["capabilities"]["live"])

    def test_invalid_rules_and_risk_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "operator"):
            compile_strategy({**STRATEGY, "entry": [{"field": "return_5", "operator": "contains", "value": 0}]})
        with self.assertRaisesRegex(ValueError, "max_position_pct"):
            compile_strategy({**STRATEGY, "risk": {**STRATEGY["risk"], "max_position_pct": 150}})


if __name__ == "__main__":
    unittest.main()
