import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(request, monkeypatch):
    """Unit and integration tests must never reach the network (PLAN.md Phases 2 and 3).

    Only tests marked local_model may talk to the local Ollama server.
    """
    if request.node.get_closest_marker("local_model"):
        return

    def refuse(*args, **kwargs):
        raise RuntimeError("tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", refuse)
