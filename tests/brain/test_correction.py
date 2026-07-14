"""Is this prompt a correction?

A cheap heuristic that runs on every single prompt, so it must be free. It is a
filter, not a judgement: the distiller (an actual model) decides what is really a
rule. False positives cost nothing. False negatives are the only real loss, so the
heuristic errs toward flagging.
"""

from hookkit.correction import looks_like_correction


def test_flags_the_storepose_correction():
    assert looks_like_correction("no, you have to live run before you push") is True


def test_flags_prohibitions():
    assert looks_like_correction("never use mp4v, it renders as green static") is True
    assert looks_like_correction("don't commit raw footage") is True
    assert looks_like_correction("stop using the legacy page") is True


def test_flags_imperatives():
    assert looks_like_correction("always rebuild web/out after touching web/") is True
    assert looks_like_correction("you need to run the tests first") is True
    assert looks_like_correction("make sure you check the frame") is True
    assert looks_like_correction("remember to update the README") is True


def test_flags_a_bare_no():
    assert looks_like_correction("no. run the pipeline first.") is True


def test_does_not_flag_a_question():
    assert looks_like_correction("what does calib/ actually do?") is False


def test_does_not_flag_a_plain_instruction():
    assert looks_like_correction("add a flag for the tracker") is False
    assert looks_like_correction("run the tests") is False


def test_does_not_flag_a_description():
    assert looks_like_correction("the dashboard shows occupancy over time") is False


def test_is_case_insensitive():
    assert looks_like_correction("NEVER use mp4v") is True


def test_does_not_match_a_word_inside_another_word():
    """'always' inside 'alwaysland' or 'no' inside 'notice' must not trip it."""
    assert looks_like_correction("notice the tracker drift") is False
    assert looks_like_correction("the nostalgic demo") is False


def test_handles_garbage():
    assert looks_like_correction("") is False
    assert looks_like_correction(None) is False
    assert looks_like_correction(123) is False
