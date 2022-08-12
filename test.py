from pathlib import Path
from time import sleep

from ambuda.tasks.pdf import split_pdf

path = "/Users/akp/temp/ramacharita/book.pdf"


r = split_pdf.delay(path)
print(r.status)
print(r.result)
while True:
    print(r.status)
    print(r.result)
    sleep(1)
