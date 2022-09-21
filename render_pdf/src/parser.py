from lxml import etree
from lxml.etree import fromstring
import json
from collections import defaultdict

data_location = "../data/text.xml"
# Can replace the below with a string 
"""
with open("../data/text.xml", 'r') as f:
    data = f.read().encode(encoding="utf-8")
    
root = fromstring(data)
"""
root = etree.parse(data_location).getroot()
root_url = root.tag.replace("TEI","").replace("{","").replace("}","")

def tagname(tag):
    return f"{{{root_url}}}{tag}"

def get_body(root):
    return root.find(tagname("text")).find(tagname("body"))

def get_title(root):
    return root.find(tagname("head")).text

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

# Can be multithreaded.  
def parse_text(root):
    verses = {}
    analysis = {}
    for child in root:
        if child.tag == tagname("lg"):
            v,txt = parse_lg(child)
            verses[v] = txt
        if child.tag == tagname("note"):
            v,txt = parse_note(child)
            analysis[v] = txt
    return verses, analysis


if __name__ == "__main__":
    verses, analysis = parse_text(get_text_div(get_body(root)))
    print(json.dumps(verses,indent=4))
