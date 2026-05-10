from io import BytesIO
from unittest.mock import MagicMock, patch

from lxml import etree

import ambuda.database as db
import ambuda.utils.text_validation as text_validation
from ambuda.utils.text_validation import Token


def _find_result(report, description):
    for group in report.groups:
        for r in group.results:
            if r.description == description:
                return r
    raise AssertionError(f"Result not found: {description!r}")


def _get_xml_from_string(blob):
    return etree.fromstring(blob)


def test_to_string_strips_namespaces():
    NS = "http://www.tei-c.org/ns/1.0"
    xml = etree.Element(f"{{{NS}}}lg")
    child = etree.SubElement(xml, f"{{{NS}}}l")
    child.text = "text"
    result = text_validation._to_string(xml)
    assert "<lg" in result
    assert "<l" in result
    assert NS not in result


def test_validate_all_blocks_have_unique_n():
    # Happy path
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg><lg n="lg2"><l>सञ्जय उवाच ।</l><l>दृष्ट्वा तु पाण्डवानीकं व्यूढं दुर्योधनस्तदा ।</l><l>आचार्यमुपसङ्गम्य राजा वचनमब्रवीत् ॥ १-२ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.UniqueBlockIds.validate_doc(xml)
    assert validation_result.num_ok == 2
    assert validation_result.num_total == 2
    assert len(validation_result.errors) == 0

    # Repeating lg1 for n
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg><lg n="lg1"><l>सञ्जय उवाच ।</l><l>दृष्ट्वा तु पाण्डवानीकं व्यूढं दुर्योधनस्तदा ।</l><l>आचार्यमुपसङ्गम्य राजा वचनमब्रवीत् ॥ १-२ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.UniqueBlockIds.validate_doc(xml)
    assert validation_result.num_ok == 1
    assert validation_result.num_total == 2
    assert len(validation_result.errors) == 1


def test_xml_is_well_formed():
    # Happy path
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.WellFormedXml.validate_doc(xml)
    assert validation_result.num_ok == 1
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 0

    # Using invalid <lgx> tag instead of <lg>
    xml = _get_xml_from_string(
        '<doc><div><lgx n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lgx></div></doc>'
    )
    validation_result = text_validation.WellFormedXml.validate_doc(xml)
    assert validation_result.num_ok == 0
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 1
    detail = validation_result.errors[0]
    assert detail["type"] == "xml"
    assert detail["messages"]
    assert "<lgx" in detail["xml"]

    # Empty <lg> fails validation
    xml = _get_xml_from_string('<doc><div><lg n="lg1"></lg></div></doc>')
    validation_result = text_validation.WellFormedXml.validate_doc(xml)
    assert validation_result.num_ok == 0
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 1
    assert "<lg> must not be empty" in validation_result.errors[0]["messages"]


def test_xml_well_formed_allows_add_with_rend_attribute():
    # <add rend="..."> is allowed inside <l>.
    xml = _get_xml_from_string(
        '<doc><div><lg n="17">'
        "<l>साम्बप्रमोदको वज्री मानसो मोदकप्रियः ।</l>"
        "<l>एकदन्तो बृहत्कुक्षिः"
        '<add rend="brackets">दीर्घतुण्डो</add>'
        "विकर्णकः ॥ १७ ॥</l>"
        "</lg></div></doc>"
    )
    validation_result = text_validation.WellFormedXml.validate_doc(xml)
    assert validation_result.num_ok == 1
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 0


def test_xml_well_formed_allows_lone_del_and_add_inside_l():
    # <del> alone (without <subst>) is allowed inside <l>.
    xml = _get_xml_from_string(
        '<doc><div><lg n="1"><l>एकदन्तो<del>बृहत्</del>कुक्षिः ॥ १ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.WellFormedXml.validate_doc(xml)
    assert validation_result.num_ok == 1
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 0


def test_xml_well_formed_allows_subst_with_del_and_add():
    # <subst> wrapping <del> and <add> is allowed inside <l>.
    xml = _get_xml_from_string(
        '<doc><div><lg n="5">'
        "<l>तादृशं परमं दिव्यं प्रत्यक्षफलदायकम् ।</l>"
        "<l>यः पठेत् प्रातरुत्थाय चिन्तयेन्मूर्ध्नि"
        "<subst><del>वे</del><add>बा</add></subst>"
        "लकम्<add>?</add>॥ ५ ॥</l>"
        "</lg></div></doc>"
    )
    validation_result = text_validation.WellFormedXml.validate_doc(xml)
    assert validation_result.num_ok == 1
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 0


def test_validate_all_sanskrit_text_is_well_formed():
    # Happy path
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.WellFormedText.validate_doc(xml)
    assert validation_result.num_ok == 4  # lg + 3 l elements
    assert validation_result.num_total == 4
    assert len(validation_result.errors) == 0

    # Text with newlines should be allowed
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र\nउवाच ।</l></lg></div></doc>'
    )
    validation_result = text_validation.WellFormedText.validate_doc(xml)
    assert len(validation_result.errors) == 0

    # Add english alphabet to trigger error
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>A धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.WellFormedText.validate_doc(xml)
    assert validation_result.num_ok == 3  # lg + 2 clean l elements
    assert validation_result.num_total == 4
    assert len(validation_result.errors) == 1


def test_well_formed_text_allows_parentheses_and_question_mark():
    # ( ) ? are allowed in Devanagari text content.
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धर्मक्षेत्रे (कुरुक्षेत्रे) ?</l></lg></div></doc>'
    )
    validation_result = text_validation.WellFormedText.validate_doc(xml)
    assert len(validation_result.errors) == 0


def test_well_formed_text_rejects_forbidden_sequences():
    # क्लृ is a common OCR artifact that should be rejected
    xml = _get_xml_from_string('<doc><div><lg n="lg1"><l>क्लृप्तम्</l></lg></div></doc>')
    validation_result = text_validation.WellFormedText.validate_doc(xml)
    assert len(validation_result.errors) == 1
    assert "क्लृ" in validation_result.errors[0]["messages"][0]

    # Without the forbidden sequence, text should pass
    xml = _get_xml_from_string('<doc><div><lg n="lg1"><l>कृतम्</l></lg></div></doc>')
    validation_result = text_validation.WellFormedText.validate_doc(xml)
    assert len(validation_result.errors) == 0


def test_validate_verse_number_if_exists():
    # Happy path: n="1.1", last verse number is १-१, rpartition(".") gives "1"
    xml = _get_xml_from_string(
        '<doc><div><lg n="1.1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.VerseNumberMatch.validate_doc(xml)
    assert validation_result.num_ok == 1
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 0

    # Mismatch: n="1.1" expects "1", but verse text has १-० (last part = "0")
    xml = _get_xml_from_string(
        '<doc><div><lg n="1.1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-० ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.VerseNumberMatch.validate_doc(xml)
    assert validation_result.num_ok == 0
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 1

    # no verse numbers provided
    xml = _get_xml_from_string(
        '<doc><div><lg n="1.1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय</l></lg></div></doc>'
    )
    validation_result = text_validation.VerseNumberMatch.validate_doc(xml)
    assert validation_result.num_ok == 0
    assert validation_result.num_total == 0
    assert len(validation_result.errors) == 0


def test_extract_verse_text_skips_ref():
    xml = _get_xml_from_string(
        '<doc><div><lg n="1">'
        "<l>नरमृगपतिवर्षालोकेनभ्रान्तनारी-</l>"
        '<l>नरदनुजसु<ref type="noteAnchor" target="#fn1">१</ref>पर्वत्रातपातालोकः ।</l>'
        "<l>करजकुलिशपालीभिन्नदैत्येन्द्रवक्षाः</l>"
        "<l>सुररिपुबलहन्ता श्रीधरोऽस्तु श्रिये वः ॥ १ ॥</l>"
        "</lg></div></doc>"
    )
    block = xml.find(".//lg")
    text = text_validation.MeterCheck._extract_verse_text(block)
    lines = text.strip().splitlines()
    assert len(lines) == 4
    # ref text "१" should not appear in the extracted lines
    assert "१" not in lines[1]
    # but the surrounding text should be joined
    assert "नरदनुजसु" in lines[1]
    assert "पर्वत्रातपातालोकः" in lines[1]


def test_extract_verse_text_subst_uses_add_no_line_break():
    # <subst><del>...</del><add>...</add></subst> should resolve to <add>'s text,
    # without leaking the whitespace/newlines between subst's children as extra lines.
    xml = _get_xml_from_string(
        '<doc><div><lg n="5">'
        "<l>तादृशं परमं दिव्यं प्रत्यक्षफलदायकम् ।</l>"
        "<l>यः पठेत् प्रातरुत्थाय चिन्तयेन्मूर्ध्नि<subst>\n"
        "      <del>वे</del>\n"
        "      <add>बा</add>\n"
        "    </subst>लकम्<add>?</add>॥ ५ ॥</l>"
        "</lg></div></doc>"
    )
    block = xml.find(".//lg")
    text = text_validation.MeterCheck._extract_verse_text(block)
    lines = text.splitlines()
    # One line per <l> — no extra breaks introduced by <subst>.
    assert len(lines) == 2
    # <add>'s text "बा" wins over <del>'s "वे", and is joined to surrounding text.
    assert "वे" not in lines[1]
    assert "बालकम्" in lines[1]


def test_extract_verse_text_uses_corr_not_sic():
    xml = _get_xml_from_string(
        '<doc><div><lg n="1">'
        "<l>taṃ hatvā ka ihopal<choice><sic>sya</sic><corr>psya</corr></choice>ti ciraṃ</l>"
        "</lg></div></doc>"
    )
    block = xml.find(".//lg")
    text = text_validation.MeterCheck._extract_verse_text(block)
    # should use corr text "psya", not sic text "sya"
    assert "psya" in text
    assert "ihopalpsya" in text
    # sic text should not appear on its own
    assert "ihopalsya" not in text


def test_validate_no_leading_trailing_spaces():
    # Happy path -- no whitespace issues
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धर्मक्षेत्रे कुरुक्षेत्रे</l></lg></div></doc>'
    )
    result = text_validation.NoLeadingTrailingSpaces.validate_doc(xml)
    assert result.num_ok == 1
    assert result.num_total == 1
    assert len(result.errors) == 0

    # Leading space
    xml = _get_xml_from_string('<doc><div><lg n="lg1"><l> धर्मक्षेत्रे</l></lg></div></doc>')
    result = text_validation.NoLeadingTrailingSpaces.validate_doc(xml)
    assert result.num_ok == 0
    assert result.num_total == 1
    assert len(result.errors) == 1
    assert result.errors[0]["type"] == "xml"
    assert "whitespace" in result.errors[0]["messages"][0].lower()

    # Trailing space
    xml = _get_xml_from_string('<doc><div><lg n="lg1"><l>धर्मक्षेत्रे </l></lg></div></doc>')
    result = text_validation.NoLeadingTrailingSpaces.validate_doc(xml)
    assert len(result.errors) == 1

    # Non-allowlisted tags are ignored
    xml = _get_xml_from_string('<doc><div><lg n="lg1"> text </lg></div></doc>')
    result = text_validation.NoLeadingTrailingSpaces.validate_doc(xml)
    assert result.num_total == 0


def _make_akshara(weight):
    """Create a mock akshara object with a .weight attribute."""

    class Akshara:
        def __init__(self, w):
            self.weight = w

    return Akshara(weight)


def test_is_shloka():
    # Valid shloka: 2 lines of 16 syllables, positions 13-15 = L, G, L
    pattern = ["G"] * 12 + ["L", "G", "L", "G"]
    line = [_make_akshara(w) for w in pattern]
    assert text_validation.MeterCheck._is_shloka([line, line]) is True
    assert text_validation.MeterCheck._is_shloka([line]) is True
    assert text_validation.MeterCheck._is_shloka([line, line, line]) is True

    # 4 lines -- too many
    assert text_validation.MeterCheck._is_shloka([line] * 4) is False

    # Wrong length
    short_line = [_make_akshara("G")] * 15
    assert text_validation.MeterCheck._is_shloka([short_line, short_line]) is False

    # Wrong pattern at position 13 (should be L)
    bad_pattern = ["G"] * 12 + ["G", "G", "L", "G"]
    bad_line = [_make_akshara(w) for w in bad_pattern]
    assert text_validation.MeterCheck._is_shloka([bad_line, bad_line]) is False


def test_is_tristubh():
    # Valid tristubh: 4 lines of 11, positions 2-10 = G L G G L L G L G
    pattern = ["L"] + ["G", "L", "G", "G", "L", "L", "G", "L", "G"] + ["G"]
    line = [_make_akshara(w) for w in pattern]
    assert text_validation.MeterCheck._is_tristubh([line] * 4) is True
    assert text_validation.MeterCheck._is_tristubh([line] * 2) is True

    # 3 lines -- not allowed
    assert text_validation.MeterCheck._is_tristubh([line] * 3) is False

    # Wrong length
    short = [_make_akshara("G")] * 10
    assert text_validation.MeterCheck._is_tristubh([short] * 4) is False

    # Wrong internal pattern
    bad_pattern = ["L"] + ["L", "L", "G", "G", "L", "L", "G", "L", "G"] + ["G"]
    bad_line = [_make_akshara(w) for w in bad_pattern]
    assert text_validation.MeterCheck._is_tristubh([bad_line] * 4) is False


def test_mark_odd_aksharas_majority_vote():
    # 3 lines, all same length. Position 0: two G, one L -> L is odd
    scan = [
        [{"text": "a", "weight": "G"}, {"text": "b", "weight": "L"}],
        [{"text": "a", "weight": "G"}, {"text": "b", "weight": "L"}],
        [{"text": "a", "weight": "L"}, {"text": "b", "weight": "L"}],
    ]
    # Create a MeterCheck with a mock chandas for the majority vote path.
    mock_chandas = MagicMock()
    mock_match = MagicMock()
    mock_match.padya = None
    mock_chandas.classify.return_value = mock_match
    with patch("ambuda.utils.text_validation._get_chandas", return_value=mock_chandas):
        meter = text_validation.MeterCheck()
    meter._mark_odd_aksharas(scan)

    assert scan[0][0]["odd"] is False  # G is majority
    assert scan[1][0]["odd"] is False
    assert scan[2][0]["odd"] is True  # L is minority
    # Position 1: all L, none odd
    assert scan[0][1]["odd"] is False
    assert scan[2][1]["odd"] is False


def test_validate_chandas():
    # Happy path -- one lg block counts as one total
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.MeterCheck.validate_doc(xml)
    assert validation_result.num_ok == 1
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 0

    # Plain prose should fail
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>अहम् गच्छामि तत्र सदा</l></lg></div></doc>'
    )
    validation_result = text_validation.MeterCheck.validate_doc(xml)
    assert validation_result.num_ok == 0
    assert validation_result.num_total == 1

    # errors should be populated with structured error info
    assert len(validation_result.errors) == 1
    detail = validation_result.errors[0]
    assert detail["n"] == "lg1"
    assert "<lg" in detail["xml"]
    assert isinstance(detail["scan"], list)
    # scan should contain at least one line with syllable dicts
    if detail["scan"]:
        for syl in detail["scan"][0]:
            assert "text" in syl
            assert "weight" in syl
            assert syl["weight"] in ("G", "L")


def test_valid_text_id():
    # Matching slug
    elem = _get_xml_from_string('<text xml:id="my-slug"/>')
    v = text_validation.ValidTextId("my-slug")
    v.process(elem)
    result = v.result()
    assert result.num_ok == 1
    assert len(result.errors) == 0

    # Mismatched slug
    elem = _get_xml_from_string('<text xml:id="wrong"/>')
    v = text_validation.ValidTextId("my-slug")
    v.process(elem)
    result = v.result()
    assert result.num_ok == 0
    assert len(result.errors) == 1
    assert "my-slug" in result.errors[0]["messages"][0]

    # Missing xml:id
    elem = _get_xml_from_string("<text/>")
    v = text_validation.ValidTextId("my-slug")
    v.process(elem)
    result = v.result()
    assert result.num_ok == 0
    assert len(result.errors) == 1


def test_head_trailer_slugs_via_streaming_pipeline():
    """Singleton head/trailer slugs are validated via the streaming pipeline.

    Regression: iterparse clears head/trailer before the parent <div> end fires,
    so checking n at div-time used to see an empty attribute.
    """
    xml = """<?xml version="1.0"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader/>
  <text xml:id="my-slug">
    <body>
      <div n="ch1">
        <head n="ch1.head">Heading</head>
        <lg n="ch1.1"><l>नमः</l></lg>
        <trailer n="ch1.trailer">End</trailer>
      </div>
    </body>
  </text>
</TEI>
""".encode()
    report = text_validation._validate_xml_bytes(BytesIO(xml), "my-slug")
    result = _find_result(
        report,
        "Singleton <head> and <trailer> slugs end with .head / .trailer",
    )
    # Both the head and trailer should be checked and pass.
    assert result.num_total == 2
    assert result.num_ok == 2
    assert result.errors == []


def test_unique_div_ids():
    # Happy path: two divs with unique n values
    v = text_validation.UniqueDivIds()
    v.process(_get_xml_from_string('<div n="1"/>'))
    v.process(_get_xml_from_string('<div n="2"/>'))
    result = v.result()
    assert result.num_ok == 2
    assert result.num_total == 2
    assert len(result.errors) == 0

    # Duplicate n value
    v = text_validation.UniqueDivIds()
    v.process(_get_xml_from_string('<div n="1"/>'))
    v.process(_get_xml_from_string('<div n="1"/>'))
    result = v.result()
    assert result.num_ok == 1
    assert result.num_total == 2
    assert len(result.errors) == 1
    assert "Duplicate" in result.errors[0]["messages"][0]

    # Missing n attribute
    v = text_validation.UniqueDivIds()
    v.process(_get_xml_from_string("<div/>"))
    result = v.result()
    assert result.num_ok == 0
    assert result.num_total == 1
    assert len(result.errors) == 1
    assert "missing" in result.errors[0]["messages"][0].lower()


def test_blocks_have_token_data_all_present():
    """All blocks have token data -- no errors."""
    token_data = {10: [Token("a", "a")], 20: [Token("b", "b")]}
    v = text_validation.BlocksHaveTokenData()
    v.process({10, 20}, token_data)
    result = v.result()

    assert result.num_ok == 2
    assert result.num_total == 2
    assert len(result.errors) == 0


def test_blocks_have_token_data_some_missing():
    """One block is missing token data -- one error."""
    token_data = {10: [Token("a", "a")]}
    v = text_validation.BlocksHaveTokenData()
    v.process({10, 20}, token_data)
    result = v.result()

    assert result.num_ok == 1
    assert result.num_total == 2
    assert len(result.errors) == 1
    assert "20" in result.errors[0]["messages"][0]


def test_blocks_have_token_data_no_session():
    """No token data (None) -- validation is skipped."""
    v = text_validation.BlocksHaveTokenData()
    v.process({10, 20}, None)
    result = v.result()

    assert result.num_total == 0
    assert len(result.errors) == 0


def test_load_token_stems_no_session():
    """Returns None when session is None."""
    result = text_validation._load_token_stems(1, None, {10, 20})
    assert result is None


def test_load_token_stems_empty_block_ids():
    """Returns empty dict when block_ids is empty."""
    mock_session = MagicMock()
    result = text_validation._load_token_stems(1, mock_session, set())
    assert result == {}


def _mock_token_session(token_rows, bp_rows=None):
    """Create a mock session for column-only token queries.

    token_rows: list of (block_id, form, base) tuples.
    bp_rows: list of (block_id, data) tuples, or None.
    """
    mock_session = MagicMock()

    def query_side_effect(*args):
        q = MagicMock()
        # Detect which query by the first column descriptor.
        first = args[0] if args else None
        if first is db.Token.block_id:
            # Token column query uses .join(...).filter(...).all()
            q.join.return_value.filter.return_value.all.return_value = token_rows
        elif first is db.BlockParse.block_id:
            # BlockParse column query uses .filter(...).all()
            q.filter.return_value.all.return_value = bp_rows or []
        else:
            q.filter.return_value.all.return_value = []
        return q

    mock_session.query.side_effect = query_side_effect
    return mock_session


def test_load_token_stems_from_tokens():
    """Token rows are used when available."""
    mock_session = _mock_token_session(
        [
            (10, "devam", "deva"),
            (10, "rAmam", "rAma"),
            (20, "sItAm", "sItA"),
        ]
    )

    result = text_validation._load_token_stems(1, mock_session, {10, 20})
    assert result is not None
    assert set(result.keys()) == {10, 20}
    assert result[10] == [("devam", "deva"), ("rAmam", "rAma")]
    assert result[20] == [("sItAm", "sItA")]


def test_load_token_stems_falls_back_to_block_parse():
    """Falls back to BlockParse when no Token rows exist."""
    mock_session = _mock_token_session(
        token_rows=[],
        bp_rows=[
            (10, "form1\tstem1\nform2\tstem2"),
            (20, "form3\tstem3"),
        ],
    )

    result = text_validation._load_token_stems(1, mock_session, {10, 20})
    assert result is not None
    assert set(result.keys()) == {10, 20}
    assert result[10] == [("form1", "stem1"), ("form2", "stem2")]
    assert result[20] == [("form3", "stem3")]


def test_load_token_stems_no_data():
    """Returns empty dict when no Token or BlockParse rows exist."""
    mock_session = _mock_token_session(token_rows=[], bp_rows=[])

    result = text_validation._load_token_stems(1, mock_session, {10, 20})
    assert result == {}


def test_token_stems_in_dictionary_all_found():
    """All stems found in kosha -- no errors."""
    mock_kosha = MagicMock()
    mock_kosha.get.return_value = ["some_entry"]  # truthy

    token_data = {10: [Token("devam", "deva"), Token("rAmam", "rAma")]}
    v = text_validation.TokenStemsInDictionary(mock_kosha)
    v.process(set(), token_data)
    result = v.result()

    assert result.num_ok == 2
    assert result.num_total == 2
    assert len(result.errors) == 0


def test_token_stems_in_dictionary_some_missing():
    """One stem missing from kosha -- one error."""
    mock_kosha = MagicMock()
    mock_kosha.get.side_effect = lambda stem: ["entry"] if stem == "deva" else []

    token_data = {10: [Token("devam", "deva"), Token("xxx", "unknown")]}
    v = text_validation.TokenStemsInDictionary(mock_kosha)
    v.process(set(), token_data)
    result = v.result()

    assert result.num_ok == 1
    assert result.num_total == 2
    assert len(result.errors) == 1
    assert "unknown" in result.errors[0]["messages"][0]


def test_token_stems_in_dictionary_deduplicates():
    """Duplicate stems are only checked once."""
    mock_kosha = MagicMock()
    mock_kosha.get.return_value = ["entry"]

    token_data = {
        10: [Token("devam", "deva"), Token("devena", "deva")],
        20: [Token("devAya", "deva")],
    }
    v = text_validation.TokenStemsInDictionary(mock_kosha)
    v.process(set(), token_data)
    result = v.result()

    # Only 1 unique stem
    assert result.num_ok == 1
    assert result.num_total == 1
    assert len(result.errors) == 0


def test_token_stems_in_dictionary_none_token_data():
    """None token data -- validation is skipped."""
    mock_kosha = MagicMock()
    v = text_validation.TokenStemsInDictionary(mock_kosha)
    v.process(set(), None)
    result = v.result()

    assert result.num_total == 0
    assert len(result.errors) == 0


def test_token_stems_in_dictionary_empty_stems():
    """Token data with no stems -- nothing to check."""
    mock_kosha = MagicMock()
    token_data = {10: []}
    v = text_validation.TokenStemsInDictionary(mock_kosha)
    v.process(set(), token_data)
    result = v.result()

    assert result.num_total == 0
    assert len(result.errors) == 0


def test_token_padas_in_dictionary_all_found():
    """All padas found in kosha -- no errors."""
    mock_kosha = MagicMock()
    mock_kosha.get.return_value = ["some_entry"]

    token_data = {10: [Token("devam", "deva"), Token("rAmam", "rAma")]}
    v = text_validation.TokenPadasInDictionary(mock_kosha)
    v.process(set(), token_data)
    result = v.result()

    assert result.num_ok == 2
    assert result.num_total == 2
    assert len(result.errors) == 0


def test_token_padas_in_dictionary_some_missing():
    """One pada missing from kosha -- one error."""
    mock_kosha = MagicMock()
    mock_kosha.get.side_effect = lambda p: ["entry"] if p == "devam" else []

    token_data = {10: [Token("devam", "deva"), Token("badform", "unknown")]}
    v = text_validation.TokenPadasInDictionary(mock_kosha)
    v.process(set(), token_data)
    result = v.result()

    assert result.num_ok == 1
    assert result.num_total == 2
    assert len(result.errors) == 1
    assert "badform" in result.errors[0]["messages"][0]


def test_token_padas_in_dictionary_deduplicates():
    """Duplicate padas are only checked once."""
    mock_kosha = MagicMock()
    mock_kosha.get.return_value = ["entry"]

    token_data = {
        10: [Token("devam", "deva"), Token("devam", "deva")],
        20: [Token("devam", "deva")],
    }
    v = text_validation.TokenPadasInDictionary(mock_kosha)
    v.process(set(), token_data)
    result = v.result()

    assert result.num_ok == 1
    assert result.num_total == 1
    assert len(result.errors) == 0


def test_token_padas_in_dictionary_none_token_data():
    """None token data -- validation is skipped."""
    mock_kosha = MagicMock()
    v = text_validation.TokenPadasInDictionary(mock_kosha)
    v.process(set(), None)
    result = v.result()

    assert result.num_total == 0
    assert len(result.errors) == 0


def test_token_padas_in_dictionary_empty():
    """Token data with no padas -- nothing to check."""
    mock_kosha = MagicMock()
    token_data = {10: []}
    v = text_validation.TokenPadasInDictionary(mock_kosha)
    v.process(set(), token_data)
    result = v.result()

    assert result.num_total == 0
    assert len(result.errors) == 0
