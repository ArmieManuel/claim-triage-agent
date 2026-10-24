import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Unit tests must never reach the network (PLAN.md Phase 2 acceptance)."""

    def refuse(*args, **kwargs):
        raise RuntimeError("unit tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", refuse)
