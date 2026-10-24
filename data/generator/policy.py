"""The generator designs ground truth against the same thresholds the agent routes with."""

from triage.rules import RoutingPolicy, load_routing_policy

__all__ = ["RoutingPolicy", "load_policy"]

load_policy = load_routing_policy
