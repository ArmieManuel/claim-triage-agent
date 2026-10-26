"""Deliberately failing test for the PLAN.md Phase 7 acceptance demo. Never merged."""

from triage.rules import load_routing_policy


def test_auto_process_limit_is_3000_euros():
    # Wrong on purpose: config/routing.yaml says 2500. CI must fail and block the merge.
    assert load_routing_policy().auto_max_amount == 3000
