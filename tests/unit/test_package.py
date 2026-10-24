import triage


def test_package_exposes_version():
    assert triage.__version__ == "0.1.0"
