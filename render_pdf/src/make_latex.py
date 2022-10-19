from dataclasses import dataclass
import sys
import os
import parser
from typing import Union

import jinja2

# TODO probably best to use pydantic for a config template for the dict below. 
@dataclass
class TextData:
    language = "sanskrit"
    title = ""
    author =  ""
    body = []
    analysis = []
    hasAnalysis = False


latex_jinja_env = jinja2.Environment(
        block_start_string = '<*',
        block_end_string = '*>',
        variable_start_string = '<<',
        variable_end_string = '>>',
        comment_start_string = '<=',
        comment_end_string = '=>',
        loader = jinja2.FileSystemLoader(os.path.abspath('.'))
    )
template = latex_jinja_env.get_template('template.tex')

## TODO add an argument for receiving language, default is sanskrit + devanagari

def generate_fields(file: str, lipi: Union["DEVA","IAST"], author: str) -> tuple[list, list, str, str]:
    # TODO handle lipi input after transliterator is built
    _ = lipi
    #####

    verses, analysis, title, parsed_author = parser.parse(data_location=file)
    if not parsed_author:
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

def generate_texfile(file_location, lipi, author):
    # TODO Author can either be passed in or extracted. Some texts don't have this. 
    body, analysis, title, author = generate_fields(file_location, lipi, author)
    data = TextData()
    data.body = body
    data.title = title.lower()
    if author:
        data.author = author.lower()
    data.analysis = analysis
    data.hasAnalysis = not analysis # Necessary flag for jinja; but would be nice to be rid of it. TODO
    rendered = template.render(vars(data))
    # Ouput naming convention is standardized.
    with open(f"./outputs/{data.title}-{data.author}.tex", 'w') as f:
        f.write(rendered)

def main():
    input_files = sys.argv[1]
    generate_texfile(input_files, "IAST", "") 
   
if __name__ == "__main__":
    main()


