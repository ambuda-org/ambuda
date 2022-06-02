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


@bp.route("/")
def index():
    return render_template("index.html", texts=TEXTS)


@bp.route("/texts/<slug>/")
def text(slug):
    text = [t for t in TEXTS if t.slug == slug][0]
    return render_template("text.html", text=text)


@bp.route("/texts/<text>/<path>/")
def section(text, path):
    text = [t for t in TEXTS if t.slug == text][0]
    section = [s for s in text.sections if s.slug == path][0]

    raw_content = section.get_content()
    content = xml.transform(raw_content)
    return render_template("section.html", text=text, section=section, content=content)
