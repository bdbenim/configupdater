from copy import deepcopy
from textwrap import dedent

import pytest

from configupdater.block import NotAttachedError
from configupdater.parser import Parser


def test_deepcopy():
    example = """\
    [options.extras_require]
    testing =   # Add here test requirements (used by tox)
        sphinx  # required for system tests
        flake8  # required for system tests
    """
    doc = Parser().read_string(dedent(example))
    section = doc["options.extras_require"]
    option = section["testing"]
    assert option.container is section

    clone = deepcopy(section)

    assert str(clone) == str(section)
    assert section.container is doc
    with pytest.raises(NotAttachedError):
        assert clone.container is None  # copies should always be created detached

    # Make sure no side effects are felt by the original when the copy is modified
    # and vice-versa
    clone["testing"] = ""
    assert str(clone) != str(section)
    assert str(doc) == dedent(example)
    clone["testing"].add_before.option("extra_option", "extra_value")
    assert "extra_option" in clone
    assert "extra_option" not in section
    assert clone["extra_option"].container is clone

    section["testing"].add_before.option("other_extra_option", "other_extra_value")
    assert "other_extra_option" in section
    assert "other_extra_option" not in clone
    assert section["other_extra_option"].container is section

    section.add_after.comment("# new comment")
    assert "# new comment" in str(doc)
    assert "# new comment" not in str(clone)

    with pytest.raises(NotAttachedError):
        clone.add_before.comment("# new comment")
