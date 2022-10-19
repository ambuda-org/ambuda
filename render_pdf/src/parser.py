import json
from collections import defaultdict
from urllib.request import urlopen

from lxml import etree
from lxml.etree import fromstring

from typing import Optional
import sys

def get_body(root):
    return root.find(tagname("text")).find(tagname("body"))

def get_title(root, alt_root) -> Optional[str]:
    # God this is ugly # TODO
    try:
        return root.find(tagname("head")).text
    except:
        try:
            root = alt_root
            tag = root.find(tagname("teiHeader"))\
                    .find(tagname("fileDesc")) \
                    .find(tagname("titleStmt"))
            # TODO Check if find('./teiHeader/fileDesc/titleStmt').text syntax will work on tag in lxml.  
            return tag.find(tagname("title")).text
        except:
            # TODO change bare execpt to catch specific errors. 
            print("[Warning] Couldn't get title.")
            return 

def get_author(root) -> Optional[str]:
    try:
            tag = root.find(tagname("teiHeader"))\
                    .find(tagname("fileDesc")) \
                    .find(tagname("titleStmt"))
            author = tag.find(tagname("author")).text
    except:
        return 
    else:
        return author

def get_text_div(root):
    return root.find(tagname("div"))

def parse_lg(lg,verse_id=None):
    phrases = defaultdict(dict)
    if not verse_id:
        verse_id = lg.get("{http://www.w3.org/XML/1998/namespace}id")
    for i, L in enumerate(lg):
        # assumes that all children in <l> are <seg> elements
        for segment in L:
            seg_index = segment.get("n")
            text = segment.text
            phrases[i][seg_index] = text
    return verse_id, phrases

def parse_note(note):
    corresp = note.get("corresp").replace("#","")

    return parse_lg(note.find(tagname("lg")), corresp)

def parse_div(div):
    verses = []
    for lg in div:
        verses.append(parse_lg(lg))
    return verses

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

def parse_from_root(root) -> (dict, dict):
    global root_url
    root_url = root.tag.replace("TEI","").replace("{","").replace("}","")
    body = get_body(root)
    verses, analysis = parse_text(get_text_div(body))
    return verses, analysis, get_title(body, root), get_author(root)


# probably need to use asyncio here? 
def parse(url=None, data_location = None):
    if url:
        with urlopen(url) as f:
            data = etree.parse(f).getroot()
        return parse_from_root(data)
    if data_location:
        with open(data_location, 'r') as f:
            data = etree.parse(f).getroot()
        return parse_from_root(data) 

if __name__ == "__main__":
    input_file, output_file = sys.argv[1], sys.argv[2]
    verses, analysis, title = parse(url=link)


