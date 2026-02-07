import xml.etree.ElementTree as ET

import ambuda.utils.text_validation as text_validation


def _get_xml_from_string(blob):
    return ET.fromstring(blob)


def test_validate_all_blocks_have_unique_n():
    # Happy path
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg><lg n="lg2"><l>सञ्जय उवाच ।</l><l>दृष्ट्वा तु पाण्डवानीकं व्यूढं दुर्योधनस्तदा ।</l><l>आचार्यमुपसङ्गम्य राजा वचनमब्रवीत् ॥ १-२ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.validate_all_blocks_have_unique_n.validate(xml)
    assert validation_result.num_ok == 1
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 0

    # Repeating lg1 for n
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg><lg n="lg1"><l>सञ्जय उवाच ।</l><l>दृष्ट्वा तु पाण्डवानीकं व्यूढं दुर्योधनस्तदा ।</l><l>आचार्यमुपसङ्गम्य राजा वचनमब्रवीत् ॥ १-२ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.validate_all_blocks_have_unique_n.validate(xml)
    assert validation_result.num_ok == 0
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 0


def test_xml_is_well_formed():
    # Happy path
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.validate_xml_is_well_formed.validate(xml)
    assert validation_result.num_ok == 1
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 0

    # Using invalid <lgx> tag instead of <lg>
    xml = _get_xml_from_string(
        '<doc><div><lgx n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lgx></div></doc>'
    )
    validation_result = text_validation.validate_xml_is_well_formed.validate(xml)
    assert validation_result.num_ok == 0
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 1

    # Verse <lg> has no content
    xml = _get_xml_from_string('<doc><div><lg n="lg1"></lg></div></doc>')
    validation_result = text_validation.validate_xml_is_well_formed.validate(xml)
    assert validation_result.num_ok == 0
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 1


def test_validate_all_sanskrit_text_is_well_formed():
    # Happy path
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg></div></doc>'
    )
    validation_result = (
        text_validation.validate_all_sanskrit_text_is_well_formed.validate(xml)
    )
    assert validation_result.num_ok == 6
    assert validation_result.num_total == 6
    assert len(validation_result.errors) == 0

    # Add english alphabet to trigger error
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>A धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg></div></doc>'
    )
    validation_result = (
        text_validation.validate_all_sanskrit_text_is_well_formed.validate(xml)
    )
    assert validation_result.num_ok == 5
    assert validation_result.num_total == 6
    assert len(validation_result.errors) == 1


def test_validate_verse_number_if_exists():
    # Happy path
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.validate_verse_number_if_exists.validate(xml)
    assert validation_result.num_ok == 1
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 0

    # verse number should be १-१ instead of १-०
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-० ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.validate_verse_number_if_exists.validate(xml)
    assert validation_result.num_ok == 0
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 1

    # no verse numbers provided
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय</l></lg></div></doc>'
    )
    validation_result = text_validation.validate_verse_number_if_exists.validate(xml)
    assert validation_result.num_ok == 0
    assert validation_result.num_total == 0
    assert len(validation_result.errors) == 0

def test_validate_chandas():
    # Happy path
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>धृतराष्ट्र उवाच ।</l><l>धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।</l><l>मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१ ॥</l></lg></div></doc>'
    )
    validation_result = text_validation.validate_chandas.validate(xml)
    assert validation_result.num_ok == 3
    assert validation_result.num_total == 3
    assert len(validation_result.errors) == 0
    
    # Satyameva Jayate should fail
    xml = _get_xml_from_string(
        '<doc><div><lg n="lg1"><l>सत्यमेव जयते</l></lg></div></doc>'
    )
    validation_result = text_validation.validate_chandas.validate(xml)
    assert validation_result.num_ok == 0
    assert validation_result.num_total == 1
    assert len(validation_result.errors) == 1
