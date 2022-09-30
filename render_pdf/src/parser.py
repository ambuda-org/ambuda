from lxml import etree
from lxml.etree import fromstring
import json
from collections import defaultdict
from urllib.request import urlopen

def get_body(root):
    return root.find(tagname("text")).find(tagname("body"))

def get_title(root, alt_root):
    # God this is ugly # TODO
    try:
        return root.find(tagname("head")).text
    except:
        try:
            root = alt_root
            tag = root.find(tagname("teiHeader"))\
                    .find(tagname("fileDesc")) \
                    .find(tagname("titleStmt"))
            return tag.find(tagname("title")).text
        except:
            print("[Warning] Couldn't get title.")
            return ""

def get_author(root):
    try:
        return root.find(tagname("titleStmt"))\
                .find(tagname("author")).text
    except:
        return ""

def get_text_div(root):
    return root.find(tagname("div"))

def parse_lg(lg,verse=None):
    phrases = defaultdict(dict)
    if not verse:
        verse = lg.get("{http://www.w3.org/XML/1998/namespace}id")
    for line, l in enumerate(lg):
        for seg in l:
            segment = seg.get("n")
            text = seg.text
            phrases[line][segment] = text
    return verse, phrases

def parse_note(note):
    corresp = note.get("corresp").replace("#","")

    return parse_lg(note.find(tagname("lg")), corresp)

def parse_div(div):
    verses = []
    for lg in div:
        verses.append(parse_lg(lg))
    return verses
# Can be multithreaded.  
def parse_text(root):
    verses = {}
    analysis = {}
    for child in root.iter():
        if child.tag == tagname("lg"):
            v,txt = parse_lg(child)
            verses[v] = txt
        if child.tag == tagname("note"):
            v,txt = parse_note(child)
            analysis[v] = txt
        """
        if child.tag == tagname("div"):
            vs = parse_div(child)
            for v in vs:
                verses[v[0]] = v[1]
        """
    return verses, analysis


# CLUNKY Fix this. Closure maybe?
root_url = ""

def tagname(tag):
    return f"{{{root_url}}}{tag}"

def parse_from_file_or_link(data_location = "../data/text.xml"):

    root = etree.parse(data_location).getroot()
    root_url = root.tag.replace("TEI","").replace("{","").replace("}","")
    verses, analysis = parse_text(get_text_div(get_body(root)))
    return verses, analysis


def parse_from_string(inpt: str) -> (dict, dict):
    """
        Broken; Don't use.
    """
    root = fromstring(inpt)
    global root_url
    root_url = root.tag.replace("TEI","").replace("{","").replace("}","")
    verses, analysis = parse_text(get_text_div(get_body(root)))
    return verses, analysis

def parse_from_root(root) -> (dict, dict):
    global root_url
    root_url = root.tag.replace("TEI","").replace("{","").replace("}","")
    print(f"[PARSING] {get_text_div(get_body(root))}")
    body = get_body(root)
    verses, analysis = parse_text(get_text_div(body))
    return verses, analysis, get_title(body, root), get_author(body)


# probably need to use asyncio here? 
def parse(url=None, xmlString = None, data_location = None):
    if url:
        with urlopen(url) as f:
            data = etree.parse(f).getroot()
        return parse_from_root(data)
    if xmlString:
        raise NotImplementedError
        return parse_from_string(xmlString)
    if data_location:
        # support for local file
        raise NotImplementedError
    

if __name__ == "__main__":
    link = "https://raw.githubusercontent.com/ambuda-org/gretil/main/1_sanskr/tei/sa_zivopaniSad.xml"
    verses, analysis, title = parse(url=link)
    print(json.dumps(verses, indent=4))
    print(title)


