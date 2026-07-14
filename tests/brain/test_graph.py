from hookkit.dash import render
from hookkit.graph import build

RULE = """---
id: {id}
severity: {severity}
trigger.tool: Bash
trigger.pattern: ^git commit
satisfied_by.receipt: live-run
stats.fired: {fired}
stats.satisfied: {satisfied}
stats.overridden: {overridden}
---

# {id}

Related: [[mp4v-green-static]]
"""


def _rule(repo, name, severity="warn", fired=0, satisfied=0, overridden=0):
    (repo / ".brain" / "rules" / (name + ".md")).write_text(
        RULE.format(id=name, severity=severity, fired=fired, satisfied=satisfied, overridden=overridden)
    )


def _note(repo, folder, name, summary="a fact", body=""):
    directory = repo / ".brain" / folder
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (name + ".md")).write_text(
        "---\nsummary: %s\n---\n\n# %s\n\n%s\n" % (summary, name, body)
    )


def test_an_empty_brain_is_an_empty_graph(repo):
    graph = build(repo / ".brain")
    assert graph == {"nodes": [], "edges": []}


def test_rules_and_notes_become_nodes(repo):
    _rule(repo, "live-run")
    _note(repo, "gotchas", "mp4v-green-static")
    kinds = sorted(n["kind"] for n in build(repo / ".brain")["nodes"])
    assert kinds == ["note", "rule"]


def test_a_wikilink_becomes_an_edge(repo):
    _rule(repo, "live-run")
    _note(repo, "gotchas", "mp4v-green-static")
    edges = build(repo / ".brain")["edges"]
    assert edges == [{"source": "live-run", "target": "mp4v-green-static"}]


def test_a_dangling_wikilink_is_not_an_edge(repo):
    """A link to a note nobody has written yet is a TODO, not a relationship."""
    _rule(repo, "live-run")  # links to mp4v-green-static, which does not exist
    assert build(repo / ".brain")["edges"] == []


def test_a_piped_wikilink_resolves_to_its_target(repo):
    _note(repo, "gotchas", "mp4v-green-static")
    _note(repo, "map", "flow", body="see [[gotchas/mp4v-green-static|the codec trap]]")
    edges = build(repo / ".brain")["edges"]
    assert {"source": "flow", "target": "mp4v-green-static"} in edges


def test_health_learning_by_default(repo):
    _rule(repo, "r")
    assert build(repo / ".brain")["nodes"][0]["health"] == "learning"


def test_health_enforced_when_blocking(repo):
    _rule(repo, "r", severity="block")
    assert build(repo / ".brain")["nodes"][0]["health"] == "enforced"


def test_health_contested_after_one_override(repo):
    _rule(repo, "r", overridden=1)
    assert build(repo / ".brain")["nodes"][0]["health"] == "contested"


def test_health_dying_on_the_last_strike(repo):
    """Two overrides means one more and it retires. The graph must show that."""
    _rule(repo, "r", overridden=2)
    node = build(repo / ".brain")["nodes"][0]
    assert node["health"] == "dying"
    assert node["strikes_left"] == 1


def test_health_earning_when_close_to_promotion(repo):
    _rule(repo, "r", satisfied=3)
    assert build(repo / ".brain")["nodes"][0]["health"] == "earning"


def test_archived_rules_appear_as_archived(repo):
    archive = repo / ".brain" / "_archive"
    archive.mkdir(parents=True)
    (archive / "dead.md").write_text("---\nid: dead\n---\n\n# Dead\n")
    node = build(repo / ".brain")["nodes"][0]
    assert node["kind"] == "archived"


def test_duplicate_edges_are_collapsed(repo):
    _note(repo, "gotchas", "a")
    _note(repo, "map", "b", body="[[a]] and again [[a]]")
    assert len(build(repo / ".brain")["edges"]) == 1


def test_a_self_link_is_not_an_edge(repo):
    _note(repo, "gotchas", "a", body="see [[a]]")
    assert build(repo / ".brain")["edges"] == []


def test_render_embeds_the_graph_and_the_repo_name(repo):
    _rule(repo, "live-run", overridden=2)
    html = render(repo / ".brain", "storepose")
    assert "storepose" in html
    assert '"health": "dying"' in html or '"health":"dying"' in html
    assert "__DATA__" not in html


def test_render_is_self_contained(repo):
    """No CDN, no external font, no network. It must work offline, forever."""
    _rule(repo, "r")
    html = render(repo / ".brain", "x")
    assert "http://" not in html.replace("http://127.0.0.1", "")
    assert "https://" not in html
    assert "<script src" not in html
    assert "@import" not in html


def test_render_escapes_content(repo):
    """Rule bodies are model-authored. They do not get to inject script tags."""
    _note(repo, "gotchas", "x", summary="safe", body="<script>alert(1)</script>")
    html = render(repo / ".brain", "x")
    assert "<script>alert(1)</script>" not in html


def test_a_note_cannot_break_out_of_the_script_tag(repo):
    """The payload is embedded inside <script>. A body containing the literal text
    '</script>' would terminate the block early and turn the rest into live HTML -
    an injection into a page served on the user's own machine. Bodies are
    model-authored, so this is untrusted input."""
    _note(repo, "gotchas", "x", body="</script><img src=x onerror=alert(1)>")
    html = render(repo / ".brain", "x")
    assert "</script><img" not in html
    assert "<\\/script>" in html


def test_the_repo_name_is_escaped(repo):
    html = render(repo / ".brain", '<img src=x onerror=alert(1)>')
    assert "<img src=x" not in html
