from dataclasses import dataclass


@dataclass
class Rule:
    start: int
    label: str


def int_to_roman(n: int) -> str:
    """Convert an integer to its roman numeral representation."""
    # Based on https://stackoverflow.com/questions/28777219
    roman = {
        1000: "m",
        500: "d",
        400: "cd",
        100: "c",
        90: "xc",
        50: "l",
        40: "xl",
        10: "x",
        9: "ix",
        5: "v",
        4: "iv",
        1: "i",
    }
    buf = []
    for r in roman.keys():
        x, y = divmod(n, r)
        buf.append(roman[r] * x)
        n -= r * x
        if n <= 0:
            break
    return "".join(buf)


def parse_page_number_spec(numbers: str) -> list[Rule]:
    """Parse the page number spec.

    This raises an exception if the spec is invalid.
    """
    rules = []
    for line in numbers.splitlines():
        start, _, label = line.partition("=")
        start = start.strip()
        label = label.strip()

        assert label
        assert start.isdigit()

        rules.append(Rule(start=int(start), label=label))

    rules = sorted(rules, key=lambda x: x.start)
    return rules


def apply_rules(num_pages: int, rules: list[Rule]):
    slugs = []

    for n in range(1, num_pages + 1):
        rule_matches = [r for r in rules if r.start <= n]
        if not rule_matches:
            slugs.append(str(n))
            continue

        # Get last matching rule, = highest precedence rule.
        rule = rule_matches[-1]
        if rule.label.isdigit():
            offset = n - rule.start
            slugs.append(str(int(rule.label) + offset))
        elif rule.label == "i":
            offset = n - rule.start
            slugs.append(int_to_roman(1 + offset))
        else:
            slugs.append(rule.label)

    return slugs
