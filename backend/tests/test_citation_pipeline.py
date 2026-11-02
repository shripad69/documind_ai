from app.services.citation_pipeline import (
    build_evidence_snippet,
    chunk_pages,
    format_context_for_prompt,
    normalize_document_text,
    resolve_citations,
    split_sentences,
)


def test_normalization_rejoins_pdf_hyphenated_words_and_chunking_keeps_sentences_whole():
    text = "MISSION PROFILE\nThe tempera-\nture stayed near -1.5°C. " + "The crew recorded a complete observation each day. " * 24
    chunks = chunk_pages([(1, text)], size=800)

    assert "temperature stayed" in normalize_document_text(text)
    assert len(chunks) > 1
    for _, content in chunks:
        assert not content.startswith("ture ")
        assert not content.endswith("tempera-")
        # Long final sentences may be the only sentence in a chunk, but chunks
        # are otherwise assembled from complete sentence units.
        assert content.strip()


def test_page_chunks_keep_primary_page_and_sentence_overlap():
    page_one = " ".join(f"Page one sentence {index} is complete." for index in range(1, 22))
    page_two = "Page two begins with a complete sentence. " + " ".join(
        f"Another page two sentence {index} is complete." for index in range(2, 20)
    )

    chunks = chunk_pages([(1, page_one), (2, page_two)], size=800, overlap_sentences=2)
    page_two_chunks = [content for page_number, content in chunks if page_number == 2]

    assert page_two_chunks
    assert "Page one sentence 20 is complete." in page_two_chunks[0]
    assert "Page one sentence 21 is complete." in page_two_chunks[0]
    assert "Page two begins with a complete sentence." in page_two_chunks[0]


def test_every_regular_chunk_starts_and_ends_on_a_sentence_boundary():
    text = " ".join(f"Sentence number {index} ends cleanly." for index in range(1, 90))
    chunks = chunk_pages([(1, text)], size=800)

    assert len(chunks) > 2
    for _, content in chunks:
        assert content.startswith("Sentence number ")
        assert content.endswith(".")
        assert all(sentence.endswith(".") for sentence in split_sentences(content))


def test_evidence_snippet_centers_the_exact_answer_fact():
    leading = "Background detail without the requested value. " * 12
    mission_chunk = leading + "The mission lasted 48 days, including the return transit. The crew landed safely."
    brine_chunk = leading + "The team collected 120 liters of brine from the subsurface reservoir. Samples were sealed."

    mission_snippet, mission_highlight = build_evidence_snippet(
        mission_chunk, "How long was the mission?", "The mission lasted 48 days."
    )
    brine_snippet, brine_highlight = build_evidence_snippet(
        brine_chunk, "How much brine was collected?", "The team collected 120 liters of brine."
    )

    assert "48 days" in mission_snippet
    assert "48 days" in mission_highlight
    assert "120 liters" in brine_snippet
    assert "120 liters" in brine_highlight
    assert len(mission_snippet) < len(mission_chunk)


def test_citation_registry_is_one_indexed_and_references_follow_first_citation_order():
    registry = {
        f"chunk_{index}": {
            "document_id": "doc-a",
            "document_name": "Project Boreas.pdf",
            "chunk_id": f"chunk-db-{index}",
            "page_number": index,
            "content": f"Evidence for value {index}.",
        }
        for index in range(1, 5)
    }
    context = format_context_for_prompt(registry)
    answer, references = resolve_citations(
        "The first fact is value 4 [chunk_4]. Another fact is value 2 [chunk_2]. Repeated [chunk_4].",
        registry,
        query="Which facts are stated?",
    )

    assert "[chunk_1] (Document: Project Boreas.pdf | Page: 1)" in context
    assert "[chunk_4] (Document: Project Boreas.pdf | Page: 4)" in context
    assert "[chunk_1]" in answer and "[chunk_2]" in answer
    assert "[chunk_4]" not in answer
    assert [reference["citation_id"] for reference in references] == ["chunk_1", "chunk_2"]
    assert [reference["citation_number"] for reference in references] == [1, 2]
    assert [reference["chunk_id"] for reference in references] == ["chunk-db-4", "chunk-db-2"]
    assert all(reference["full_text"] for reference in references)


def test_uncited_answer_has_no_source_references_and_cited_snippet_has_full_fact():
    registry = {
        "chunk_1": {
            "document_id": "doc-a", "document_name": "Project Boreas.pdf", "chunk_id": "db-1",
            "page_number": 1, "content": "Context. " * 70 + "The mission lasted 48 days.",
        },
    }
    answer, references = resolve_citations("Please clarify which mission you mean.", registry, query="mission")
    assert answer == "Please clarify which mission you mean."
    assert references == []

    _, references = resolve_citations("The mission lasted 48 days [chunk_1].", registry, query="How long?")
    assert "48 days" in references[0]["snippet"]
    assert "48 days" in references[0]["full_text"]
    assert "48 days" in references[0]["highlight_text"]


def test_numeric_claim_is_rebound_to_the_chunk_that_contains_its_exact_value():
    registry = {
        "chunk_1": {
            "document_id": "doc-a", "document_name": "Project Boreas.pdf", "chunk_id": "mission",
            "page_number": 1, "content": "The mission lasted 48 days.",
        },
        "chunk_2": {
            "document_id": "doc-a", "document_name": "Project Boreas.pdf", "chunk_id": "brine",
            "page_number": 3, "content": "The reservoir yielded 120 liters of brine.",
        },
    }

    answer, references = resolve_citations(
        "The mission lasted 48 days [chunk_2]. The reservoir yielded 120 liters [chunk_1].",
        registry,
        query="What were the mission duration and brine volume?",
    )

    assert answer == "The mission lasted 48 days [chunk_1]. The reservoir yielded 120 liters [chunk_2]."
    assert [reference["chunk_id"] for reference in references] == ["mission", "brine"]
    assert "48 days" in references[0]["snippet"]
    assert "120 liters" in references[1]["snippet"]


def test_numeric_day_compound_in_source_supports_answer_in_days():
    registry = {
        "chunk_1": {
            "document_id": "doc-a", "document_name": "Project Boreas.pdf", "chunk_id": "mission",
            "page_number": 1, "content": "Project Boreas was a 48-day deep-ice drilling reconnaissance mission.",
        },
    }

    answer, references = resolve_citations(
        "Project Boreas lasted 48 days [chunk_1].", registry, query="How long did it last?"
    )

    assert answer == "Project Boreas lasted 48 days [chunk_1]."
    assert references[0]["page_number"] == 1
    assert "48-day" in references[0]["snippet"]

