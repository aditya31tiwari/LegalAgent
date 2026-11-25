"""Clause-vs-Indian-law flagging: corroboration helpers (no Kev server needed)."""
from legalagent.core import statutory_kev as sk


def test_bump_raises_and_caps():
    assert sk.bump("low", 0) == "low"
    assert sk.bump("low", 1) == "medium"
    assert sk.bump("medium", 1) == "high"
    assert sk.bump("medium", 2) == "high"
    assert sk.bump("high", 1) == "high"


def test_mapped_section_for_each_category():
    assert sk.mapped_section("restraint_of_trade") == ("The Indian Contract Act, 1872", "27")
    assert sk.mapped_section("penalty_or_forfeiture") == ("The Indian Contract Act, 1872", "74")
    assert sk.mapped_section("one_sided_arbitrator") == ("The Arbitration and Conciliation Act, 1996", "12")
    assert sk.mapped_section("none") is None


def test_law_confirmed_only_when_retrieval_finds_the_mapped_section():
    s27 = {"act": "The Indian Contract Act, 1872", "section": "27"}
    s74 = {"act": "The Indian Contract Act, 1872", "section": "74"}
    assert sk.law_confirmed("restraint_of_trade", [s74, s27])
    assert not sk.law_confirmed("restraint_of_trade", [s74])
    assert not sk.law_confirmed("none", [s27])


def test_every_category_maps_to_a_section_in_the_library():
    from legalagent.core.statutes import load_library
    lib = {(s["act"], str(s["section"])) for s in load_library()}
    for cat in sk.CATEGORIES:
        key = sk.mapped_section(cat)
        if key:
            assert key in lib, f"{cat} maps to {key}, not in the India Code library"
