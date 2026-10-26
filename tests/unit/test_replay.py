import json

import pytest

from evals.run_eval import main as run_eval_main
from tests.unit.test_eval import perfect_model
from triage.config import Settings
from triage.llm import FakeProvider, make_provider
from triage.llm.replay import CassetteMissError, RecordingProvider, ReplayProvider, cassette_key


def test_cassette_key_depends_on_every_input():
    base = cassette_key("s", "p", {"type": "object"})
    assert base == cassette_key("s", "p", {"type": "object"})
    assert base != cassette_key("s2", "p", {"type": "object"})
    assert base != cassette_key("s", "p2", {"type": "object"})
    assert base != cassette_key("s", "p", None)


def test_recorded_answers_replay_exactly(tmp_path):
    path = tmp_path / "cassette.json"
    recorder = RecordingProvider(FakeProvider(["one", "two"]))
    first = recorder.generate(system="s", prompt="a")
    second = recorder.generate(system="s", prompt="b", schema={"x": 1})
    recorder.save(path)

    replay = ReplayProvider(path)
    assert replay.generate(system="s", prompt="b", schema={"x": 1}).content == second.content
    again = replay.generate(system="s", prompt="a")
    assert (again.content, again.prompt_tokens, again.output_tokens) == (
        first.content,
        first.prompt_tokens,
        first.output_tokens,
    )


def test_replay_miss_explains_how_to_fix_it(tmp_path):
    path = tmp_path / "cassette.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(CassetteMissError, match="re-record"):
        ReplayProvider(path).generate(system="s", prompt="changed prompt")


def test_make_provider_can_replay(tmp_path):
    path = tmp_path / "cassette.json"
    path.write_text("{}", encoding="utf-8")
    provider = make_provider(Settings(llm_provider="replay", cassette_path=path))
    assert isinstance(provider, ReplayProvider)


def test_an_evaluation_can_be_recorded_and_replayed(tmp_path):
    cassette = tmp_path / "ci.json"
    no_gates = tmp_path / "none.yaml"
    common = ["--cases", "case_013", "case_018", "--thresholds", str(no_gates)]
    run_eval_main(
        [*common, "--out", str(tmp_path / "a"), "--record", str(cassette)],
        provider=FakeProvider(perfect_model),
    )
    assert len(json.loads(cassette.read_text(encoding="utf-8"))) == 6  # 3 model calls per case
    run_eval_main([*common, "--out", str(tmp_path / "b")], provider=ReplayProvider(cassette))

    def metrics(folder):
        (report,) = list((tmp_path / folder).iterdir())
        return json.loads((report / "metrics.json").read_text(encoding="utf-8"))["metrics"]

    recorded, replayed = metrics("a"), metrics("b")
    for name in ("routing_accuracy", "field_accuracy_mean", "classification_accuracy"):
        assert recorded[name] == replayed[name]
