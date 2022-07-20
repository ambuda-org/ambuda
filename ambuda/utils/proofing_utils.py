TEI_HEADER_BOILERPLATE = """
<?xml version="1.0" encoding="UTF-8"?>
<!-- This file was automatically generated. Please review it for markup mistakes. -->
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>TODO</title>
        <author>TODO</author>
      </titleStmt>
      <publicationStmt>
        <publisher>Ambuda</publisher>
        <availability>
          TODO
        </availability>
      </publicationStmt>
    </fileDesc>
  </teiHeader>
  <text>
    <body>
""".strip()


def transform_blob_to_page(blob: str) -> str:
    """Parses blob into text as page (linebreaks removed)."""
    page_buf = []
    for line in blob.splitlines():
        line = line.strip()
        # Join hyphens
        if line.endswith("-"):
            page_buf.append(line[:-1])
        else:
            # FIXME: we should also join lines if a paragraph, but we
            # can reliably separate paragraphs/verses only if there's
            # markup.
            page_buf.append(line)
            page_buf.append("\n")
    return "".join(page_buf)


def to_plain_text(blobs: list[str]) -> str:
    """Publish a project as plain text."""
    return "\n\n".join([transform_blob_to_page(b) for b in blobs])


def to_tei_xml(blobs: list[str]) -> str:
    """Publish a project as TEI XML."""
    # FIXME: add much more TEI boilerplate
    buf = [TEI_HEADER_BOILERPLATE]
    for i, blob in enumerate(blobs):
        page_number = i + 1
        buf.append(f'<pb n="{page_number}" />')
        clean_page_content = transform_blob_to_page(blob)
        buf.append(clean_page_content)

    buf.append("</body></text></TEI>")
    return "\n\n".join(buf)
