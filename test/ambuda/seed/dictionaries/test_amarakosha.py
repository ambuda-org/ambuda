import re

from ambuda.seed.dictionaries.amarakosha import create_entries


def test_create_entries():
    raw_key = "स्वर्ग"
    raw_body = "स्वर्ग a<br><br>b<br><br>c<br><br>d<br><br>e<br><br>f<br><br>g"

    results = list(create_entries(raw_key, raw_body))
    assert len(results) == 1

    key, body = results[0]
    assert key == "svarga"
    assert re.match(".*<lex>a</lex> b.*c.*<cite>d</cite>", body)
