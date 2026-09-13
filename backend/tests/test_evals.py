"""
Integration test for the extraction evaluation suite.
Verifies that the hand-labelled benchmark dataset loads and computes accuracy >= 85% in mock mode.
"""

import pytest
from evals.eval_extraction import run_evaluation


@pytest.mark.asyncio
async def test_extraction_eval_suite_mock():
    accuracy, scores = await run_evaluation(mock_mode=True)
    assert len(scores) == 10
    assert accuracy >= 0.85
    for s in scores:
        assert s.error is None
        assert s.overall_sample_score >= 0.70
