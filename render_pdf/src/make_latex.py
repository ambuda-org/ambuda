from typing import Union
import parser
import os
import jinja2

# TODO probably best to use pydantic for a config template for the dict below. 
data = {
        'language' : "sanskrit",
        'title' : "",
        'author' : "",
        'body' : [],
        'analysis': []
    }

os.chdir("../tex_files")
latex_jinja_env = jinja2.Environment(
        block_start_string = '((*',
        block_end_string = '*))',
        variable_start_string = '(((',
        variable_end_string = ')))',
        comment_start_string = '((=',
        comment_end_string = '=))',
        loader = jinja2.FileSystemLoader(os.path.abspath('.'))
    )
template = latex_jinja_env.get_template('template.tex')

## TODO add an argument for receiving language, default is sanskrit + devanagari

def write_tex(tex: str):
    os.chdir("../tex_files")
    with open("./template.tex", 'w') as f:
        f.write(tex)

def generate_fields(link: str, lipi: Union["SKT","IAST"], author: str) -> tuple[list, str, str]:
    # TODO handle lipi input
    _ = lipi
    #####

    verses, analysis, title, parsed_author = parser.parse(url=link)
    if parsed_author != "":
        author = parsed_author
    parsed_verses = []
    parsed_analysis = []
    
    for verse in verses:
        for line in verses[verse]:
            l = [verse]
            for segment in verses[verse][line]:
                text = verses[verse][line][segment]
                l.append(text)
            parsed_verses.append(l)
    for verse in analysis:
        for line in verses[verse]:
            l = [verse]
            for segment in verses[verse][line]:
                text = verses[verse][line][segment]
                l.append(text)
            parsed_analysis.append(l)

    return parsed_verses, parsed_analysis, title, author

def generate_texfile(link, lipi, author):
    # TODO Author can either be passed in or extracted. Some texts don't have this. 
    # Need to standardize input texts. 
    body, analysis, title, author = generate_fields(link, lipi, author)
    print(f"[Title] {title}")
    print(f"[Author] {author}")
    global data
    data['body'] = body
    data['title'] = title
    data['author'] = author
    data['analysis'] = analysis
    if analysis == []:
        data['hasAnalysis'] = False
    else:
        data['hasAnalysis'] = True
    rendered = template.render(data)
    with open("../tex_files/output.tex", 'w') as f:
        f.write(rendered)
def generate_pdf(link: str, lipi: Union["SKT","IAST"], author: str):
    generate_texfile(link, lipi, author)
    os.chdir("../tex_files")
    os.system("fish runscript")

def main():
    link = "https://raw.githubusercontent.com/ambuda-org/gretil/main/1_sanskr/tei/sa_kAlidAsa-kumArasaMbhava.xml"
    generate_pdf(link, "IAST", "apauruṣeya") 
   
if __name__ == "__main__":
    main()


