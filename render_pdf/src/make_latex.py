from typing import Union
import parser
import os

BASE = r"""
\documentclass{tufte-handout}

\title{::main title::}

\author{::author::}

%\date{28 March 2010} % without \date command, current date is supplied

%\geometry{showframe} % display margins for debugging page layout

\usepackage{graphicx} % allow embedded images
  \setkeys{Gin}{width=\linewidth,totalheight=\textheight,keepaspectratio}
  \graphicspath{{graphics/}} % set of paths to search for images
\usepackage{amsmath}  % extended mathematics
\usepackage{booktabs} % book-quality tables
\usepackage{units}    % non-stacked fractions and better unit spacing
\usepackage{multicol} % multiple column layout facilities
\usepackage{lipsum}   % filler text
\usepackage{fancyvrb} % extended verbatim environments
  \fvset{fontsize=\normalsize}% default font size for fancy-verbatim environments

% Standardize command font styles and environments
\newcommand{\doccmd}[1]{\texttt{\textbackslash#1}}% command name -- adds backslash automatically
\newcommand{\docopt}[1]{\ensuremath{\langle}\textrm{\textit{#1}}\ensuremath{\rangle}}% optional command argument
\newcommand{\docarg}[1]{\textrm{\textit{#1}}}% (required) command argument
\newcommand{\docenv}[1]{\textsf{#1}}% environment name
\newcommand{\docpkg}[1]{\texttt{#1}}% package name
\newcommand{\doccls}[1]{\texttt{#1}}% document class name
\newcommand{\docclsopt}[1]{\texttt{#1}}% document class option name
\newenvironment{docspec}{\begin{quote}\noindent}{\end{quote}}% command specification environment

\usepackage[parfill]{parskip}
\usepackage{fontspec}
\usepackage[english]{babel}
\usepackage{microtype}

% Sanskrit Support %
\babelprovide[import]{sanskrit-devanagari}
\babelprovide[import]{english}
\babelprovide[import]{greek}
\babelprovide[import]{german}
\babelfont[english]{rm}{Bitter}
\babelfont[sanskrit-devanagari]{rm}
          {Siddhanta}
\babelfont[sanskrit-devanagari]{sf}
          [Language=Default]{Noto Sans}

          
\newcommand\textsanskrit[1]{\foreignlanguage{sanskrit-devanagari}{#1}}
\newenvironment{sanskrit}%
{\begin{otherlanguage}{sanskrit-devanagari}}%
{\end{otherlanguage}}
%%%%%%%%%%%%%%%%%%


\begin{document}
\maketitle

::verses::

\end{document}
"""


def set_title(base: str, title:str) -> str:
    return base.replace(r"::main title::",title)

def set_author(base: str, author: Union[str,None]) -> str:
    if author:
        return base.replace(r"::author::", author)
    else:
        return base.replace(r"\\author{::author::}", "")

def set_verses(base: str, verses: str) -> str:
    return base.replace(r"::verses::", verses)

def write_tex(tex: str):
    os.chdir("../tex_files")
    with open("./template.tex", 'w') as f:
        f.write(tex)

def generate_texfile(link: str, lipi: Union["SKT","IAST"], author: str) -> str:
    verses, analysis, title = parser.parse(url=link)
    latex = ""
    if lipi == "SKT":
        begin = r"\begin{sanskrit}"
        end = r"\end{sanskrit}"
    else:
        begin = ""
        end = ""

    for verse in verses:
        v = f"\\ {verse}" + r"\\"
        for line in verses[verse]:
            for segment in verses[verse][line]:
                text = verses[verse][line][segment]
                if segment in "bd":
                    v+=text+r"\\"
                else:
                    v+=text+" "
        latex+=f"{begin} {v}\\ {end}"
    tex = set_title(BASE, title)
    tex = set_author(tex, author)
    tex = set_verses(tex,latex)
    write_tex(tex)

def generate_pdf(link: str, lipi: Union["SKT","IAST"], author: str):
    generate_texfile(link, lipi, author)
    os.chdir("../tex_files")
    os.system("fish runscript")


if __name__ == "__main__":
    link = "https://raw.githubusercontent.com/ambuda-org/gretil/main/1_sanskr/tei/sa_zivopaniSad.xml"
    generate_pdf(link, "IAST", "apauruṣeya") 
    
