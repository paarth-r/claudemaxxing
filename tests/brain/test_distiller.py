"""The distiller is the only component that calls a model, so it is the only one
that takes untrusted input from one. Three properties matter more than the feature:

  1. It can never write outside .brain/. A model-authored path is untrusted.
  2. The model never sets its own enforcement level. New rules are born `warn`.
  3. A failed distillation loses nothing. Queues drain only on success.
"""

import json

from hookkit import queue
from hookkit.distiller import apply, build_prompt, parse_response, run
from hookkit.rules import load_rules


def test_parse_a_bare_json_array():
    ops = parse_response('[{"path": "rules/x.md", "content": "hello"}]')
    assert ops == [{"path": "rules/x.md", "content": "hello"}]


def test_parse_a_fenced_json_block():
    text = 'Here is what I learned:\n```json\n[{"path": "gotchas/y.md", "content": "z"}]\n```\nDone.'
    ops = parse_response(text)
    assert ops[0]["path"] == "gotchas/y.md"


def test_parse_garbage_returns_empty():
    assert parse_response("I could not find anything worth recording.") == []
    assert parse_response("") == []
    assert parse_response(None) == []


def test_parse_rejects_non_list_json():
    assert parse_response('{"path": "x"}') == []


def test_parse_skips_malformed_entries():
    ops = parse_response('[{"path": "rules/a.md", "content": "ok"}, {"nope": 1}, "junk"]')
    assert len(ops) == 1


def test_apply_writes_under_brain(repo):
    written = apply(repo / ".brain", [{"path": "gotchas/mp4v.md", "content": "use avc1"}])
    assert (repo / ".brain" / "gotchas" / "mp4v.md").read_text() == "use avc1"
    assert written == ["gotchas/mp4v.md"]


def test_apply_rejects_path_traversal(repo):
    written = apply(repo / ".brain", [{"path": "../../../etc/passwd", "content": "pwned"}])
    assert written == []
    assert not (repo.parent / "etc").exists()


def test_apply_rejects_absolute_paths(repo):
    written = apply(repo / ".brain", [{"path": "/tmp/brain-pwned.md", "content": "x"}])
    assert written == []


def test_apply_rejects_sneaky_traversal(repo):
    written = apply(repo / ".brain", [{"path": "rules/../../escape.md", "content": "x"}])
    assert written == []
    assert not (repo / "escape.md").exists()


def test_apply_rejects_writes_to_protected_dirs(repo):
    """The model may not forge receipts, and may not resurrect its own archived rules."""
    assert apply(repo / ".brain", [{"path": "_receipts/fake.jsonl", "content": "x"}]) == []
    assert apply(repo / ".brain", [{"path": "_archive/back.md", "content": "x"}]) == []


def test_a_new_rule_is_always_born_warn(repo):
    """Never trust a model to set its own enforcement level."""
    content = "---\nid: r\nseverity: block\ntrigger.tool: Bash\ntrigger.pattern: ^git\nsatisfied_by.receipt: k\n---\n\nBody\n"
    apply(repo / ".brain", [{"path": "rules/r.md", "content": content}])
    written = (repo / ".brain" / "rules" / "r.md").read_text()
    assert "severity: warn" in written
    assert "severity: block" not in written


def test_a_rule_with_no_severity_gets_warn(repo):
    content = "---\nid: r\ntrigger.tool: Bash\ntrigger.pattern: ^git\nsatisfied_by.receipt: k\n---\n\nBody\n"
    apply(repo / ".brain", [{"path": "rules/r.md", "content": content}])
    assert load_rules(repo / ".brain")[0].severity == "warn"


def test_non_rule_files_are_not_touched(repo):
    content = "# A gotcha\n\nseverity: block is just prose here\n"
    apply(repo / ".brain", [{"path": "gotchas/g.md", "content": content}])
    assert (repo / ".brain" / "gotchas" / "g.md").read_text() == content


def test_build_prompt_includes_existing_rule_ids(repo):
    prompt = build_prompt(repo / ".brain", [], [], "", ["live-run-before-commit"])
    assert "live-run-before-commit" in prompt


def test_build_prompt_includes_the_flat_key_schema(repo):
    prompt = build_prompt(repo / ".brain", [], [], "", [])
    assert "trigger.pattern" in prompt
    assert "satisfied_by.receipt" in prompt


def test_build_prompt_includes_the_corrections(repo):
    prompt = build_prompt(
        repo / ".brain", [{"prompt": "never use mp4v"}], [], "", []
    )
    assert "never use mp4v" in prompt


def test_run_writes_what_the_model_returns(repo):
    push_correction(repo)
    ops = json.dumps([{"path": "rules/mp4v.md", "content": rule_text()}])
    written = run(repo / ".brain", "sess", None, call_model=lambda _: ops)
    assert written == ["rules/mp4v.md"]
    assert load_rules(repo / ".brain")[0].id == "no-mp4v"


def test_run_drains_the_queue_on_success(repo):
    push_correction(repo)
    ops = json.dumps([{"path": "rules/mp4v.md", "content": rule_text()}])
    run(repo / ".brain", "sess", None, call_model=lambda _: ops)
    assert queue.peek(repo / ".brain", "corrections") == []


def test_a_failed_distillation_keeps_the_queue(repo):
    """Nothing is lost. The correction waits for the next session."""
    push_correction(repo)

    def boom(_):
        raise RuntimeError("claude is down")

    assert run(repo / ".brain", "sess", None, call_model=boom) == []
    assert len(queue.peek(repo / ".brain", "corrections")) == 1


def test_a_garbage_response_keeps_the_queue(repo):
    push_correction(repo)
    assert run(repo / ".brain", "sess", None, call_model=lambda _: "sorry, no") == []
    assert len(queue.peek(repo / ".brain", "corrections")) == 1


def test_run_does_nothing_with_an_empty_queue_and_no_transcript(repo):
    assert run(repo / ".brain", "sess", None, call_model=lambda _: "[]") == []


def push_correction(repo):
    queue.push(repo / ".brain", "corrections", {"prompt": "never use mp4v, use avc1"})


def rule_text():
    return (
        "---\n"
        "id: no-mp4v\n"
        "severity: warn\n"
        "trigger.tool: Bash\n"
        "trigger.pattern: mp4v\n"
        "satisfied_by.receipt: never\n"
        "---\n\n"
        "# Never use mp4v\n"
    )
