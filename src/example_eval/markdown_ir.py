from __future__ import annotations

import re
from html import unescape
from typing import Iterable

from bs4 import BeautifulSoup

from .types import Block, DocumentIR, TableIR

_CODE_FENCE_RE = re.compile(r"^```(?P<lang>[A-Za-z0-9_+-]*)\s*$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.*)$")
_HTML_TABLE_START_RE = re.compile(r"<table\b", re.IGNORECASE)
_HTML_TABLE_END_RE = re.compile(r"</table>", re.IGNORECASE)


def normalize_text(text: str, *, collapse_whitespace: bool = True) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = unescape(text)
    text = re.sub(r"<div\b[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<center>|</center>", "", text, flags=re.IGNORECASE)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"`([^`]+)`", r"\1", text)
    lines = [line.strip() for line in text.split("\n")]
    if collapse_whitespace:
        text = "\n".join(line for line in lines if line != "")
        text = re.sub(r"[ \t]+", " ", text)
    else:
        text = "\n".join(lines)
    return text.strip()


def _split_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _is_pipe_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    line = lines[index].strip()
    separator = lines[index + 1].strip()
    if "|" not in line or "|" not in separator:
        return False
    return bool(re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", separator))


def _collect_until_blank(lines: list[str], start: int) -> tuple[list[str], int]:
    collected: list[str] = []
    index = start
    while index < len(lines) and lines[index].strip() != "":
        collected.append(lines[index])
        index += 1
    return collected, index


def _parse_markdown_table(lines: list[str]) -> TableIR:
    rows: list[list[str]] = []
    for idx, raw_line in enumerate(lines):
        if idx == 1 and set(raw_line.replace("|", "").replace(":", "").replace("-", "").strip()) == set():
            continue
        line = raw_line.strip().strip("|")
        cells = [normalize_text(cell) for cell in line.split("|")]
        rows.append(cells)
    return TableIR(rows=rows, source="markdown")


def _parse_html_table(table_text: str) -> TableIR:
    soup = BeautifulSoup(table_text, "html.parser")
    table = soup.find("table")
    if table is None:
        return TableIR(rows=[], source="html")
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = [normalize_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    return TableIR(rows=rows, source="html")


def parse_markdown_document(text: str) -> DocumentIR:
    lines = _split_lines(text)
    blocks: list[Block] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped == "":
            index += 1
            continue

        fence_match = _CODE_FENCE_RE.match(stripped)
        if fence_match:
            language = (fence_match.group("lang") or "").lower()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            raw = "\n".join(code_lines)
            if language in {"text", "plaintext"}:
                nested = parse_markdown_document(raw)
                if nested.blocks:
                    blocks.extend(nested.blocks)
                else:
                    blocks.append(
                        Block(
                            kind="paragraph",
                            raw_text=raw,
                            canonical_text=normalize_text(raw, collapse_whitespace=False),
                            meta={"language": language, "from_fence": True},
                        )
                    )
            else:
                blocks.append(
                    Block(
                        kind="code",
                        raw_text=raw,
                        canonical_text=normalize_text(raw, collapse_whitespace=False),
                        meta={"language": language},
                    )
                )
            continue

        if stripped == "$$":
            formula_lines: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != "$$":
                formula_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            raw = "\n".join(formula_lines)
            blocks.append(
                Block(kind="formula", raw_text=raw, canonical_text=normalize_text(raw, collapse_whitespace=False))
            )
            continue

        if _HTML_TABLE_START_RE.search(stripped):
            table_lines = [line]
            index += 1
            while index < len(lines) and not _HTML_TABLE_END_RE.search(lines[index]):
                table_lines.append(lines[index])
                index += 1
            if index < len(lines):
                table_lines.append(lines[index])
                index += 1
            raw = "\n".join(table_lines)
            blocks.append(
                Block(kind="table", raw_text=raw, canonical_text=normalize_text(raw), table=_parse_html_table(raw))
            )
            continue

        if _is_pipe_table_start(lines, index):
            table_lines, index = _collect_until_blank(lines, index)
            raw = "\n".join(table_lines)
            blocks.append(
                Block(
                    kind="table",
                    raw_text=raw,
                    canonical_text=normalize_text(raw),
                    table=_parse_markdown_table(table_lines),
                )
            )
            continue

        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text_part = heading_match.group(2)
            blocks.append(
                Block(
                    kind="heading",
                    raw_text=line,
                    canonical_text=normalize_text(text_part),
                    meta={"level": level},
                )
            )
            index += 1
            continue

        list_match = _LIST_RE.match(line)
        if list_match:
            items, index = _collect_until_blank(lines, index)
            for item in items:
                match = _LIST_RE.match(item)
                payload = match.group(1) if match else item
                blocks.append(Block(kind="list_item", raw_text=item, canonical_text=normalize_text(payload)))
            continue

        paragraph_lines, index = _collect_until_blank(lines, index)
        raw = "\n".join(paragraph_lines)
        blocks.append(Block(kind="paragraph", raw_text=raw, canonical_text=normalize_text(raw)))

    return DocumentIR(blocks=blocks)


def join_block_text(blocks: Iterable[Block]) -> str:
    return "\n".join(block.canonical_text for block in blocks if block.canonical_text)
