import socket

import pytest

OLLAMA_PORT = 11434
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def no_network(request, monkeypatch):
    """Tests must never reach the network or the local model (PLAN.md Phases 2 and 3).

    Loopback connections are allowed, because asyncio on Windows connects a socket pair to
    itself for its event loop (FastAPI's TestClient needs one). The Ollama port stays blocked.
    Only tests marked local_model may talk to the local Ollama server.
    """
    if request.node.get_closest_marker("local_model"):
        return
    real_connect = socket.socket.connect

    def guarded(self, address):
        if isinstance(address, tuple) and address[0] in LOOPBACK and address[1] != OLLAMA_PORT:
            return real_connect(self, address)
        raise RuntimeError(f"tests must not open network connections (tried {address})")

    monkeypatch.setattr(socket.socket, "connect", guarded)
