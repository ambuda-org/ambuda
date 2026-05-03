"""Prompt template substitution for batch LLM operations.

Templates use {key} placeholders. `expand` substitutes only the keys provided,
leaving any others (e.g. {content} for per-page substitution downstream) intact.
"""


def expand(template: str, **vars: str) -> str:
    result = template
    for key, value in vars.items():
        result = result.replace("{" + key + "}", value)
    return result


def placeholders(template: str) -> set[str]:
    """Return the set of {key} placeholders present in the template."""
    import re

    return set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", template))
