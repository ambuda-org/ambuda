""""""


def standardize_tokens(tokens: list[Token]):
    """Standardize token text in place."""

    # Most users expect and prefer the visarga as opposed to a word-final "s"
    # or "r".
    for t in tokens:
        if t.text.endswith("s") or t.text.endswith("r"):
            t.text = t.text[:-1] + "H"
