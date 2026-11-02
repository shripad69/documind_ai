"""Sentence-aligned chunking and deterministic citation helpers for workspace RAG."""

from __future__ import annotations

import html
import re
from collections import defaultdict
from typing import Any


CITATION_TAG_RE = re.compile(r"\[(chunk_\d+)\]", re.IGNORECASE)
_WORD_RE = re.compile(r"\d+(?:[.,]\d+)*(?:%|°[A-Za-z]+)?|[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’][A-Za-z]+)?")
_QUANTITY_RE = re.compile(
    r"(?P<number>[+-]?\d[\d,]*(?:\.\d+)?)\s*[-–—]?\s*"
    r"(?P<unit>°\s?[CF]|[A-Za-zµμ%]+(?:\s*/\s*[A-Za-zµμ]+)?)?",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from", "had", "has",
    "have", "in", "into", "is", "it", "its", "of", "on", "or", "that", "the", "their", "this",
    "to", "was", "were", "what", "when", "where", "which", "who", "with", "would",
}
_ABBREVIATIONS = {
    "dr.", "fig.", "no.", "vs.", "p.", "pp.", "e.g.", "i.e.", "etc.", "mr.", "mrs.", "ms.",
    "prof.", "inc.", "approx.", "dept.", "st.", "u.s.", "u.k.",
}


def normalize_document_text(text: str) -> str:
    """Normalize extraction noise while retaining paragraph and heading boundaries."""
    text = str(text or "").replace("\ufeff", "").replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    # Rejoin words hyphenated by PDF line wrapping (e.g. tempera-\nture).
    text = re.sub(r"(?<=[A-Za-z])-[ \t]*\n[ \t]*(?=[A-Za-z])", "", text)
    text = re.sub(r"[ \t]*\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text)

    paragraphs: list[str] = []
    for raw_paragraph in re.split(r"\n\s*\n", text):
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw_paragraph.split("\n")]
        lines = [line for line in lines if line]
        if not lines:
            continue

        # Keep recognizable headings on their own boundary. Other single line
        # breaks are PDF line wraps and become spaces so sentences stay intact.
        current: list[str] = []
        for line in lines:
            if _looks_like_heading(line):
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
                paragraphs.append(line)
            else:
                current.append(line)
        if current:
            paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs).strip()


def _looks_like_heading(line: str) -> bool:
    letters = [character for character in line if character.isalpha()]
    if len(line) <= 120 and len(letters) >= 3 and all(character.isupper() for character in letters):
        return True
    return bool(
        len(line) <= 100
        and re.match(r"^\s*\d+(?:\.\d+)*[.)]?\s+[A-Z][\w\s,:&()/–—-]*$", line)
        and not re.search(r"[.!?]$", line)
    )


def split_sentences(text: str) -> list[str]:
    """Split at sentence endings without treating decimals or common abbreviations as endings."""
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return []
    pieces: list[str] = []
    start = 0
    for match in re.finditer(r"[.!?](?:[\"'’”)}\]]*)?(?=\s+|$)", normalized):
        end = match.end()
        punctuation = normalized[match.start()]
        if punctuation == ".":
            before = normalized[:match.start() + 1]
            token_match = re.search(r"(?:^|\s)([^\s]+)$", before)
            token = token_match.group(1).casefold() if token_match else before.casefold()
            if re.search(r"\d\.\d$", before) or token in _ABBREVIATIONS:
                continue
            # Keep initials and dotted acronyms together (e.g. "J. R." and "U.S.").
            if re.search(r"(?:\b[A-Za-z]\.){1,3}$", before):
                continue
        sentence = normalized[start:end].strip()
        if sentence:
            pieces.append(sentence)
        start = end
        while start < len(normalized) and normalized[start].isspace():
            start += 1
    tail = normalized[start:].strip()
    if tail:
        pieces.append(tail)
    return pieces


def _page_sentence_units(page_number: int, text: str) -> list[tuple[int, str, str]]:
    """Return (page, sentence, separator-before) units for one extracted page."""
    normalized = normalize_document_text(text)
    units: list[tuple[int, str, str]] = []
    paragraphs = normalized.split("\n\n") if normalized else []
    pending_heading: str | None = None
    for paragraph_index, paragraph in enumerate(paragraphs):
        if _looks_like_heading(paragraph):
            pending_heading = paragraph
            continue
        sentences = split_sentences(paragraph)
        for sentence_index, sentence in enumerate(sentences):
            if pending_heading:
                sentence = f"{pending_heading}\n{sentence}"
                pending_heading = None
            separator = "\n\n" if paragraph_index and sentence_index == 0 else (" " if sentence_index else "")
            units.append((page_number, sentence, separator))
    return units


def chunk_pages(
    pages: list[tuple[int, str]],
    size: int = 800,
    overlap_sentences: int = 2,
) -> list[tuple[int, str]]:
    """Chunk pages at sentence boundaries with up to two complete sentences of overlap.

    Chunks target 600–900 characters. A single sentence longer than that remains
    whole rather than being split mid-sentence. The page number records the first
    sentence that is new to the chunk; carried context from the prior page does
    not change that primary page attribution.
    """
    target = max(600, min(int(size), 900))
    lower_bound = min(600, target)
    upper_bound = max(900, target)
    results: list[tuple[int, str]] = []
    previous_page_tail: list[tuple[int, str, str]] = []

    for page_number, raw_text in pages:
        units = _page_sentence_units(page_number, raw_text)
        if not units:
            continue
        cursor = 0
        carry = previous_page_tail[-overlap_sentences:] if overlap_sentences and previous_page_tail else []

        def passage_length(selected_units: list[tuple[int, str, str]]) -> int:
            if not selected_units:
                return 0
            return sum(len(sentence) for _, sentence, _ in selected_units) + sum(
                len(separator) for _, _, separator in selected_units[1:]
            )

        while cursor < len(units):
            first_novel = cursor
            selected: list[tuple[int, str, str]] = list(carry) if cursor == 0 else []
            selected_length = passage_length(selected)

            # Preserve as much of the two-sentence overlap as fits alongside
            # the next complete sentence. Oversized sentences remain intact.
            while selected and selected_length + len(units[cursor][2]) + len(units[cursor][1]) > upper_bound:
                selected.pop(0)
                selected_length = passage_length(selected)

            while cursor < len(units):
                _, sentence, separator = units[cursor]
                candidate_length = selected_length + len(separator) + len(sentence)
                novel_count = cursor - first_novel
                if selected and novel_count > 0 and candidate_length > upper_bound:
                    break
                if selected and novel_count > 0 and selected_length >= lower_bound and candidate_length > target:
                    break
                selected.append(units[cursor])
                selected_length = candidate_length
                cursor += 1
                if selected_length >= target:
                    break

            # A page carry alone must never create a duplicate-only chunk.
            if cursor == first_novel:
                selected = []
                _, sentence, separator = units[cursor]
                selected.append(units[cursor])
                selected_length = len(sentence) + len(separator)
                cursor += 1

            content_parts: list[str] = []
            for index, (_, sentence, separator) in enumerate(selected):
                if index:
                    content_parts.append(separator or " ")
                content_parts.append(sentence)
            content = "".join(content_parts).strip()
            if content:
                results.append((page_number, content))

            # The next page starts with this page's last complete sentences. The
            # next chunk on this same page gets the same two-sentence overlap.
            carry = selected[-overlap_sentences:] if overlap_sentences else []

        previous_page_tail = units[-overlap_sentences:] if overlap_sentences else []

    return results


def format_context_for_prompt(citation_registry: dict[str, dict[str, Any]]) -> str:
    """Render the exact registry contents with explicit, escaped chunk boundaries."""
    formatted: list[str] = ["<retrieved_context>"]
    for citation_id, chunk in citation_registry.items():
        document_name = html.escape(str(chunk.get("document_name") or "Unknown document"), quote=True)
        page_number = html.escape(str(chunk.get("page_number") or 1), quote=True)
        chunk_id = html.escape(str(chunk.get("chunk_id") or ""), quote=True)
        content = html.escape(str(chunk.get("content") or ""), quote=False)
        formatted.append(
            f'<context_chunk id="{citation_id}" document_name="{document_name}" '
            f'page_number="{page_number}" chunk_id="{chunk_id}">\n'
            f'[{citation_id}] (Document: {document_name} | Page: {page_number})\n'
            f"{content}\n</context_chunk>"
        )
    formatted.append("</retrieved_context>")
    return "\n\n".join(formatted)


def _answer_sentence_for_citation(answer: str, position: int) -> str:
    prefix = answer[:position].rstrip()
    if prefix.endswith((".", "?", "!")):
        prefix = prefix[:-1].rstrip()
    boundaries = [prefix.rfind(mark) for mark in (". ", "? ", "! ", "\n")]
    start = max(boundaries)
    start = 0 if start < 0 else start + (1 if prefix[start:start + 1] == "\n" else 2)
    sentence = prefix[start:].strip(" \t\r\n-*•")
    return CITATION_TAG_RE.sub("", sentence).strip()


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in _WORD_RE.findall(text or "")]


def _quantities(text: str) -> set[tuple[str, str]]:
    quantities = set()
    for match in _QUANTITY_RE.finditer(text or ""):
        number = match.group("number").replace(",", "")
        unit = re.sub(r"\s+", "", match.group("unit") or "").casefold()
        if unit and unit not in {"%", "°c", "°f"} and "/" not in unit and unit.endswith("s"):
            unit = unit[:-1]
        quantities.add((number, unit))
    return quantities


def _supports_explicit_quantities(answer_sentence: str, chunk_text: str) -> bool:
    quantities = _quantities(answer_sentence)
    if not quantities:
        return True
    source_quantities = _quantities(chunk_text)
    for number, unit in quantities:
        if unit:
            if (number, unit) not in source_quantities:
                return False
        elif not any(source_number == number for source_number, _ in source_quantities):
            return False
    return True


def build_evidence_snippet(
    chunk_text: str,
    query: str,
    answer_sentence: str,
    *,
    max_characters: int = 480,
) -> tuple[str, str]:
    """Choose a fact-centered preview and return it with the exact matched sentence."""
    sentences = split_sentences(normalize_document_text(chunk_text))
    original = str(chunk_text or "").strip()
    if not sentences:
        return original, original

    query_tokens = set(_tokens(query)) - _STOP_WORDS
    answer_tokens = set(_tokens(answer_sentence)) - _STOP_WORDS
    answer_numbers = {token for token in answer_tokens if any(character.isdigit() for character in token)}
    focus_tokens = query_tokens | answer_tokens

    def score(sentence: str) -> int:
        tokens = set(_tokens(sentence))
        overlap = tokens & focus_tokens
        value = sum(1 for token in overlap if not any(character.isdigit() for character in token))
        value += 6 * len(tokens & answer_numbers)
        value += 3 * sum(1 for token in overlap if any(character.isdigit() for character in token))
        return value

    best_index = max(range(len(sentences)), key=lambda index: (score(sentences[index]), -index))
    highlight = sentences[best_index]
    limit = max(1, int(max_characters))
    left = best_index
    right = best_index + 1
    selected_length = len(highlight)

    # Add adjacent evidence first, while always retaining the full best sentence.
    for candidate_index in (best_index - 1, best_index + 1):
        if candidate_index < 0 or candidate_index >= len(sentences):
            continue
        candidate = sentences[candidate_index]
        additional = len(candidate) + 1
        if selected_length + additional <= limit:
            if candidate_index < best_index:
                left = candidate_index
            else:
                right = candidate_index + 1
            selected_length += additional

    snippet = " ".join(sentences[left:right]).strip()
    return snippet, highlight


def resolve_citations(
    answer: str,
    citation_registry: dict[str, dict[str, Any]],
    *,
    query: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Resolve only valid cited tags, then renumber answer and references by first use."""
    occurrences: list[tuple[re.Match[str], str | None, str]] = []
    for match in CITATION_TAG_RE.finditer(answer):
        requested_tag = match.group(1).lower()
        sentence = _answer_sentence_for_citation(answer, match.start())
        selected_tag = requested_tag if requested_tag in citation_registry else None
        requested_text = str(citation_registry.get(requested_tag, {}).get("content") or "")

        # Numeric claims can be checked deterministically. If the model points at
        # the wrong retrieved chunk, bind the citation to a chunk that contains
        # every number and unit in that answer sentence.
        if selected_tag and not _supports_explicit_quantities(sentence, requested_text):
            sentence_tokens = set(_tokens(sentence)) - _STOP_WORDS
            candidates = []
            for registry_tag, chunk in citation_registry.items():
                content = str(chunk.get("content") or "")
                if _supports_explicit_quantities(sentence, content):
                    overlap = len(sentence_tokens & (set(_tokens(content)) - _STOP_WORDS))
                    candidates.append((overlap, registry_tag))
            selected_tag = max(candidates, key=lambda candidate: candidate[0])[1] if candidates else None

        occurrences.append((match, selected_tag, sentence))

    cited_tags = list(dict.fromkeys(tag for _, tag, _ in occurrences if tag is not None))
    replacement = {tag: f"chunk_{index}" for index, tag in enumerate(cited_tags, start=1)}
    replacement_by_position = {match.start(): replacement[tag] if tag else None for match, tag, _ in occurrences}

    def replace_tag(match: re.Match[str]) -> str:
        citation_id = replacement_by_position.get(match.start())
        return f"[{citation_id}]" if citation_id else ""

    normalized_answer = CITATION_TAG_RE.sub(replace_tag, answer)
    answer_sentences: dict[str, list[str]] = defaultdict(list)
    for _, tag, sentence in occurrences:
        if tag and sentence:
            answer_sentences[tag].append(sentence)

    references: list[dict[str, Any]] = []
    for citation_number, citation_tag in enumerate(cited_tags, start=1):
        chunk = citation_registry[citation_tag]
        content = str(chunk.get("content") or "")
        cited_sentences = answer_sentences.get(citation_tag) or []
        evidence_query = " ".join(cited_sentences)
        snippet, highlight = build_evidence_snippet(content, query, evidence_query)
        references.append({
            "citation_id": replacement[citation_tag],
            "citation_number": citation_number,
            "document_id": str(chunk.get("document_id") or ""),
            "file_name": str(chunk.get("document_name") or "Unknown document"),
            "page_number": chunk.get("page_number"),
            "chunk_id": str(chunk.get("chunk_id") or ""),
            "snippet": snippet,
            "full_text": content,
            "highlight_text": highlight,
        })
    return normalized_answer.strip(), references

