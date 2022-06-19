from xml.etree import ElementTree as ET

import pytest

from ambuda.utils.parse_alignment import (
    num_vowels,
    _iter_text_with_parent,
    get_padas_for_text,
)
from ambuda.utils.cheda import Token


@pytest.mark.parametrize(
    "chunk,expected",
    [
        ("rAma", 2),
        ("rAmaH", 2),
        ("rAm", 1),
    ],
)
def test_num_vowels(chunk, expected):
    assert num_vowels(chunk) == expected


def test_iter_xml_with_parent():
    xml = ET.fromstring("<p>This is a <span>test</span> function.</p>")
    records = list(_iter_text_with_parent(xml))
    records = [(x, y.tag, z) for x, y, z in records]
    assert records == [
        ("This is a ", "p", "text"),
        ("test", "span", "text"),
        (" function.", "span", "tail"),
    ]


@pytest.mark.parametrize(
    "text,token_strings,num_kept",
    [
        # Basic case
        ("Darmakzetre", ["Darma", "kzetre", "iti"], 2),
        # Vowel sandhi -- vowel deleted
        ("itItItIti", ["iti"] * 5, 4),
        # Visarga sandhi -- second deleted
        ("asesesese", ["ase"] * 5, 4),
        ("asosososo", ["aso"] * 5, 4),
    ],
)
def test_get_padas_for_text(text, token_strings, num_kept):
    tokens = [Token(t, "", "", False) for t in token_strings]
    chunks = get_padas_for_text(text, iter(tokens))
    assert chunks[0].tokens == tokens[:num_kept]
