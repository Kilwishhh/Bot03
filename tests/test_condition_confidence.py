"""P0-01: Condition confidence (N/M hits/total) — regression tests."""

import pytest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from app.strategy.condition_engine import (
    ConditionResult,
    evaluate_condition,
    evaluate_condition_groups,
    evaluate_condition_groups_with_results,
)
from app.strategy.scanner import _compute_confidence, _minimum_hits_for_strategy
from app.strategy.indicators import compute_indicator_votes
from app.exchange.models import Candle


class TestEvaluateConditionGroupsWithResults:
    def test_no_conditions_returns_zero_hits(self):
        config = {"logic": "all", "groups": [{"logic": "all", "conditions": []}]}
        matched, reasons, results = evaluate_condition_groups_with_results(config, {}, None)
        assert matched is True
        assert len(results) == 0

    def test_all_passed_returns_hits_equals_total(self):
        config = {
            "logic": "all",
            "groups": [
                {
                    "logic": "all",
                    "conditions": [
                        {"field": "RSI_14", "op": "<", "value": 30},
                        {"field": "EMA_50", "op": ">", "value": 50000},
                    ],
                }
            ],
        }
        values = {"RSI_14": 25.0, "EMA_50": 55000.0}
        matched, reasons, results = evaluate_condition_groups_with_results(config, values, None)
        assert matched is True
        assert len(results) == 2
        assert sum(1 for r in results if r.passed) == 2

    def test_partial_hits_returns_correct_n_over_m(self):
        config = {
            "logic": "all",
            "groups": [
                {
                    "logic": "all",
                    "conditions": [
                        {"field": "RSI_14", "op": "<", "value": 30},
                        {"field": "EMA_50", "op": ">", "value": 50000},
                        {"field": "MACD", "op": ">", "value": 0},
                    ],
                }
            ],
        }
        # Only RSI hits (25 < 30); EMA and MACD do not
        values = {"RSI_14": 25.0, "EMA_50": 49000.0, "MACD": -1.5}
        matched, reasons, results = evaluate_condition_groups_with_results(config, values, None)
        # All-logic requires ALL conditions to pass → matched is False
        assert matched is False
        assert len(results) == 3
        hits = sum(1 for r in results if r.passed)
        assert hits == 1

    def test_any_logic_hits_partial(self):
        config = {
            "logic": "any",
            "groups": [
                {
                    "logic": "all",
                    "conditions": [
                        {"field": "RSI_14", "op": "<", "value": 30},
                        {"field": "EMA_50", "op": ">", "value": 50000},
                    ],
                }
            ],
        }
        values = {"RSI_14": 50.0, "EMA_50": 49000.0}
        matched, reasons, results = evaluate_condition_groups_with_results(config, values, None)
        assert matched is False  # neither condition passed
        assert sum(1 for r in results if r.passed) == 0

    def test_condition_results_fields_are_populated(self):
        config = {
            "logic": "all",
            "groups": [
                {
                    "logic": "all",
                    "conditions": [
                        {"field": "RSI_14", "op": "<", "value": 30},
                    ],
                }
            ],
        }
        values = {"RSI_14": 25.0}
        matched, reasons, results = evaluate_condition_groups_with_results(config, values, None)
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, ConditionResult)
        assert r.field == "RSI_14"
        assert r.passed is True
        assert "25" in r.reason  # reason includes actual value

    def test_empty_config_returns_empty_results(self):
        matched, reasons, results = evaluate_condition_groups_with_results(None, {}, None)
        assert matched is True
        assert results == []

    def test_denominator_derived_from_config_not_hardcoded(self):
        # Verify denominator = number of leaf conditions, never a magic constant
        for num_conditions in [1, 2, 5, 13]:
            conditions = [
                {"field": f"IND_{i}", "op": ">", "value": 0}
                for i in range(num_conditions)
            ]
            config = {
                "logic": "all",
                "groups": [{"logic": "all", "conditions": conditions}],
            }
            matched, reasons, results = evaluate_condition_groups_with_results(config, {}, None)
            assert len(results) == num_conditions


class TestEvaluateConditionConfidenceLegacyUnchanged:
    """The original evaluate_condition_groups() must remain unchanged for callers
    that don't need per-condition results."""

    def test_still_returns_two_tuple(self):
        config = {
            "logic": "all",
            "groups": [
                {
                    "logic": "all",
                    "conditions": [{"field": "RSI_14", "op": "<", "value": 30}],
                }
            ],
        }
        values = {"RSI_14": 25.0}
        result = evaluate_condition_groups(config, values, None)
        assert isinstance(result, tuple)
        assert len(result) == 2  # (matched, reasons)
        matched, reasons = result
        assert matched is True


class TestIntegerConfidenceGate:
    def test_minimum_hits_is_integer_and_bounded(self):
        assert _minimum_hits_for_strategy({"minimum_hits": 5}, 10) == 5
        assert _minimum_hits_for_strategy({"minimum_hits": 99}, 10) == 10
        assert _minimum_hits_for_strategy({"minimum_hits": 0}, 10) == 1

    def test_quality_is_hits_over_total_without_percentage_semantics(self):
        assert _compute_confidence(5, 10, {"minimum_hits": 5}) == 0.5
        assert _compute_confidence(7, 7, {"minimum_hits": 5}) == 1.0

    def test_core_indicator_voting_config_is_directional(self):
        start = datetime(2026, 1, 1, tzinfo=UTC)
        candles = [
            Candle(start + timedelta(minutes=i), Decimal(str(100 + i)), Decimal(str(101 + i)),
                   Decimal(str(99 + i)), Decimal(str(100 + i)), Decimal("100"), start + timedelta(minutes=i + 1))
            for i in range(70)
        ]
        votes = compute_indicator_votes(candles, [
            {"name": "MACD", "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9}},
            {"name": "EMA_CROSSOVER", "params": {"fast_period": 20, "slow_period": 50}},
            {"name": "VOLUME", "params": {"period": 20}},
            {"name": "STOCHASTIC", "params": {"k_period": 14, "d_period": 3, "smooth": 3}},
        ])
        assert len(votes) == 4
        assert votes[0]["vote"] in {"LONG", "SHORT", "NEUTRAL"}
        assert votes[1]["vote"] == "LONG"
        assert all("long_enabled" in vote and "short_enabled" in vote for vote in votes)
