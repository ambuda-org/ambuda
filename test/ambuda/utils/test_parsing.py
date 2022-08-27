import pytest

from ambuda.utils.cheda import readable_parse


@pytest.mark.parametrize(
    ["raw", "expected"],
    [
        ("pos=n,g=m,c=1,n=s", "noun, masculine nominative singular"),
        ("pos=a,g=f,c=2,n=d", "adjective, feminine accusative dual"),
        ("pos=va,g=n,c=3,n=p", "participle, neuter instrumental plural"),
        ("pos=v,p=3,n=s,l=lat", "verb, third-person singular present"),
        ("pos=v,p=2,n=s,l=ashirlin", "verb, second-person singular benedictive"),
        ("pos=n,g=m,comp=y", "noun, compounded"),
        ("pos=i", "indeclinable"),
    ],
)
def test_readable_parse(raw, expected):
    assert readable_parse(raw) == expected
