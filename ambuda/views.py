import json
from dataclasses import dataclass
from pathlib import Path

from flask import Blueprint, render_template, url_for

from ambuda import xml

bp = Blueprint("site", __name__)


PROJECT_DIR = Path(__file__).parent.parent
TEXTS_DIR = PROJECT_DIR / "texts"


@dataclass
class Section:
    text: str
    title: str
    slug: str

    @property
    def url(self):
        return url_for("site.section", text=self.text, path=self.slug)

    def get_content(self) -> str:
        path = TEXTS_DIR / self.text / f"{self.slug}.xml"
        with path.open() as f:
            return f.read()


@dataclass
class Text:
    title: str
    slug: str
    sections: list[Section]

    @property
    def url(self):
        return url_for("site.text", slug=self.slug)


def _prev_cur_next(sections: list[Section], slug: str):
    found = True
    for i, s in enumerate(sections):
        if s.slug == slug:
            found = True
            break
    
    if not found:
        raise Exception(f"Unknown slug {slug}")

    prev = sections[i-1] if i > 0 else None
    cur = sections[i]
    next = sections[i+1] if i < len(sections) + 1 else None
    return prev, cur, next


def parse_texts() -> list[Text]:
    texts = []
    for folder in TEXTS_DIR.iterdir():
        metadata = folder / "index.json"
        with metadata.open() as f:
            data = json.load(f)

        text_slug = data["slug"]
        sections = [Section(text=text_slug, **x) for x in data["sections"]]
        text = Text(title=data["title"], slug=text_slug, sections=sections)
        texts.append(text)
    return texts


TEXTS = parse_texts()


def _section_groups(sections):
    grouper = {}
    for s in sections:
        key, _, _ = s.slug.rpartition('.')
        if key not in grouper:
            grouper[key] = []
        grouper[key].append(s)
    return grouper



@bp.route("/")
def index():
    return render_template("index.html", texts=TEXTS)


@bp.route("/texts/<slug>/")
def text(slug):
    text = [t for t in TEXTS if t.slug == slug][0]
    section_groups = _section_groups(text.sections)
    return render_template("text.html", text=text, section_groups=section_groups)


@bp.route("/texts/<text>/<path>/")
def section(text, path):
    text = [t for t in TEXTS if t.slug == text][0]
    prev, cur, next = _prev_cur_next(text.sections, path)

    raw_content = cur.get_content()
    content = xml.transform(raw_content)
    return render_template("section.html", text=text,
            prev=prev,
            section=cur,
            next=next,
            section_groups = _section_groups(text.sections),
            content=content)
