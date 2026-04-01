"""Schema for the reader API."""

from dataclasses import dataclass


@dataclass
class Block:
    #: The block's slug
    slug: str
    #: HTML content for the given block.
    mula: str
    #: URL to edit this block in the proofing interface (if available)
    page_url: str | None = None
    #: Parent blocks (for translations/commentaries)
    parent_blocks: list["Block"] | None = None


@dataclass
class Section:
    text_title: str
    section_title: str
    section_slug: str
    #: The blocks for this section.
    blocks: list[Block]
    prev_url: str
    next_url: str
