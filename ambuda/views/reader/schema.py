"""Schema for the reader API."""

from dataclasses import dataclass


@dataclass
class Block:
    #: The block's slug
    slug: str
    #: HTML content for the given block.
    mula: str


@dataclass
class Section:
    text_title: str
    section_title: str
    #: The blocks for this section.
    blocks: list[Block]
    prev_url: str
    next_url: str
