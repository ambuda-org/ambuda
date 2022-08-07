import fitz as pymupdf


mat = pymupdf.Matrix(4, 4)
doc = pymupdf.open("/Users/akp/temp/hamsasandesha/hamsa.pdf")
for page in doc:
    pix = page.get_pixmap(matrix=mat)
    pix.save("%i.jpg" % page.number)
    print(page.number)
print("done")
