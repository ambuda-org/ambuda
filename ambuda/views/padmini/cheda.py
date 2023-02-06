from vidyut.cheda import Token
from ambuda.views.padmini.resources import get_chedaka


def _standardize_tokens(tokens: list[Token]):
    """Standardize token text in place."""

    # Most users expect and prefer the visarga as opposed to a word-final "s"
    # or "r".
    for t in tokens:
        if t.text.endswith("s") or t.text.endswith("r"):
            # TODO: text end not writable?
            pass  # t.text = t.text[:-1] + "H"


def create_results(slp1_query: str) -> list[Token]:
    """Handle the user's query and create a result set."""

    chedaka = get_chedaka()
    try:
        tokens = chedaka.run(slp1_query)
    except Exception:
        # TODO: For now, use an exhaustive exception guard. As `vidyut`
        # matures, see if we can avoid most or all exceptions here.
        tokens = []

    _standardize_tokens(tokens)
    return tokens
