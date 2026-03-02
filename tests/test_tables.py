from example_eval.markdown_ir import parse_markdown_document
from example_eval.text_metrics import score_table_blocks


def test_html_and_markdown_tables_score_as_equivalent() -> None:
    html = "<table><tr><th>A</th><th>B</th></tr><tr><td>x</td><td>y</td></tr></table>"
    md = """| A | B |
| --- | --- |
| x | y |"""

    html_doc = parse_markdown_document(html)
    md_doc = parse_markdown_document(md)

    score, details = score_table_blocks(html_doc.table_blocks, md_doc.table_blocks)
    assert score is not None
    assert score > 0.99
    assert details["tables"][0]["subscores"]["shape"] > 0.99
