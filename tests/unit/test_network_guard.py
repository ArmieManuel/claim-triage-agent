import socket

import pytest


@pytest.mark.parametrize("address", [("127.0.0.1", 11434), ("localhost", 11434), ("8.8.8.8", 53)])
def test_the_guard_blocks_ollama_and_the_internet(address):
    with socket.socket() as sock, pytest.raises(RuntimeError, match="network"):
        sock.connect(address)
