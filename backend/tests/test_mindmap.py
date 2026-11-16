"""Unit tests for mind map generator and schema normalization."""

import json
import uuid
import pytest
from unittest.mock import MagicMock

from app.services.mindmap_generator import MindMapGenerator, MindMapGenerationError
from app.models.schemas import MindMapNodeSchema


def test_prepare_document_text_within_limit():
    chunks = ["Chunk 1 content.", "Chunk 2 content.", "Chunk 3 content."]
    prepared = MindMapGenerator.prepare_document_text(chunks, max_chars=1000)
    assert "Chunk 1 content." in prepared
    assert "Chunk 2 content." in prepared
    assert "Chunk 3 content." in prepared


def test_prepare_document_text_samples_large_documents():
    chunks = [f"Chunk number {i} with substantial detailed textual content for testing." for i in range(50)]
    prepared = MindMapGenerator.prepare_document_text(chunks, max_chars=1200)
    assert len(prepared) <= 1500
    assert "Chunk number 0" in prepared
    assert "Chunk number 49" in prepared
    assert "[... content omitted for brevity ...]" in prepared


def test_parse_and_validate_clean_json():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    valid_data = {
        "id": "root",
        "label": "Machine Learning Overview",
        "query": "Summarize Machine Learning Overview",
        "children": [
            {
                "id": "supervised",
                "label": "Supervised Learning",
                "query": "Explain Supervised Learning in detail",
                "children": [
                    {
                        "id": "regression",
                        "label": "Linear Regression",
                        "query": "How does linear regression work?",
                        "children": [],
                    }
                ],
            },
            {
                "id": "unsupervised",
                "label": "Unsupervised Learning",
                "query": "Explain Unsupervised Learning",
                "children": [],
            },
        ],
    }

    result = generator._parse_and_validate(json.dumps(valid_data), default_title="Fallback Title")
    assert result["id"] == "root"
    assert result["label"] == "Machine Learning Overview"
    assert len(result["children"]) == 2
    assert result["children"][0]["children"][0]["label"] == "Linear Regression"


def test_parse_and_validate_handles_markdown_code_fences():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    raw = """```json
    {
        "id": "root",
        "label": "Deep Learning",
        "query": "Explain Deep Learning",
        "children": [
            {"id": "cnn", "label": "CNN Architectures", "query": "What are CNNs?", "children": []}
        ]
    }
    ```"""
    result = generator._parse_and_validate(raw, default_title="Fallback Title")
    assert result["id"] == "root"
    assert result["label"] == "Deep Learning"
    assert len(result["children"]) == 1


def test_parse_and_validate_handles_surrounding_commentary():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    raw = """Here is the structured mind map you requested:

    {
        "id": "root",
        "label": "Quantum Computing",
        "query": "Explain Quantum Computing",
        "children": [
            {"id": "qubits", "label": "Qubits", "query": "What are qubits?", "children": []}
        ]
    }

    I hope this helps your research!"""
    result = generator._parse_and_validate(raw, default_title="Fallback Title")
    assert result["id"] == "root"
    assert result["label"] == "Quantum Computing"
    assert len(result["children"]) == 1


def test_parse_and_validate_assigns_missing_and_duplicate_ids():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    malformed_ids = {
        "label": "Document Root",
        "children": [
            {"label": "Child A", "children": []},
            {"id": "duplicate", "label": "Child B", "children": []},
            {"id": "duplicate", "label": "Child C", "children": []},
        ],
    }
    result = generator._parse_and_validate(json.dumps(malformed_ids), default_title="Root Document")
    assert result["id"] == "root"
    child_ids = [child["id"] for child in result["children"]]
    assert len(set(child_ids)) == 3  # All unique!
    assert child_ids[0] == "root-1"


def test_parse_and_validate_rejects_unparseable_content():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    with pytest.raises(MindMapGenerationError) as exc_info:
        generator._parse_and_validate("Sorry, I cannot produce JSON for this request.", default_title="Test")
    assert exc_info.value.status_code == 502


def test_generate_requires_non_empty_chunks():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    with pytest.raises(MindMapGenerationError) as exc_info:
        generator.generate([], "Doc", uuid.uuid4())
    assert exc_info.value.status_code == 400


def test_parse_and_validate_repairs_truncated_json():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    truncated = '{"id": "root", "label": "Project Boreas", "query": "Summarize", "children": [{"id": "node-1", "label": "Mission", "query": "Explain'
    result = generator._parse_and_validate(truncated, default_title="Project")
    assert result["id"] == "root"
    assert result["label"] == "Project Boreas"
    assert len(result["children"]) == 1
    assert result["children"][0]["label"] == "Mission"


def test_generate_invokes_openrouter_directly():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    mock_openrouter = MagicMock()
    mock_openrouter.generate.return_value = json.dumps({
        "id": "root",
        "label": "Deep Ocean Expedition",
        "query": "Summarize Deep Ocean Expedition",
        "children": [
            {"id": "trenches", "label": "Mariana Trench", "query": "Mariana details", "children": []}
        ],
    })
    generator.openrouter_generator = mock_openrouter

    result = generator.generate(["Deep sea trench exploration."], "Ocean Doc", uuid.uuid4())
    assert result["label"] == "Deep Ocean Expedition"
    assert len(result["children"]) == 1
    mock_openrouter.generate.assert_called_once()
    assert not hasattr(generator, "gemini_client")


def test_generate_end_to_end_with_mocked_llm():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    mock_llm = MagicMock()
    mock_llm.generate.return_value = json.dumps({
        "id": "root",
        "label": "Solar Energy",
        "query": "Explain Solar Energy",
        "children": [
            {"id": "pv", "label": "Photovoltaics", "query": "How PV cells work", "children": []}
        ],
    })
    generator.openrouter_generator = mock_llm

    result = generator.generate(["Solar panels absorb sunlight."], "Solar Energy Doc", uuid.uuid4())
    assert result["label"] == "Solar Energy"
    assert len(result["children"]) == 1
    mock_llm.generate.assert_called_once()


def test_parse_and_validate_strips_think_tags_and_markdown():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    nemotron_output = """<think>
We need to generate a hierarchical mind map.
The document covers RAG Evaluation Benchmarks.
Let's create 3 categories:
1. Retrieval Metrics
2. Answer Quality
3. Latency Benchmarks
Now let's format it in JSON.
</think>
```json
{
    "id": "root",
    "label": "RAG Evaluation",
    "query": "Summarize RAG Evaluation",
    "children": [
        {
            "id": "retrieval",
            "label": "Retrieval Metrics",
            "query": "Explain Retrieval Metrics",
            "children": [
                {"id": "mrr", "label": "MRR & NDCG", "query": "What is MRR?", "children": []}
            ]
        },
        {
            "id": "quality",
            "label": "Answer Quality",
            "query": "Explain Answer Quality",
            "children": []
        }
    ]
}
```"""
    result = generator._parse_and_validate(nemotron_output, default_title="Fallback Title")
    assert result["id"] == "root"
    assert result["label"] == "RAG Evaluation"
    assert len(result["children"]) == 2
    assert result["children"][0]["label"] == "Retrieval Metrics"
    assert result["children"][0]["children"][0]["label"] == "MRR & NDCG"


def test_parse_and_validate_rejects_empty_children_root():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    empty_children_output = json.dumps({
        "id": "root",
        "label": "Single Node",
        "query": "Summarize",
        "children": [],
    })
    with pytest.raises(MindMapGenerationError) as exc_info:
        generator._parse_and_validate(empty_children_output, default_title="Single Node Doc")
    assert exc_info.value.status_code == 502
    assert "zero branches" in str(exc_info.value)


def test_parse_and_validate_handles_alternative_key_names():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    alternative_keys = json.dumps({
        "title": "Document Architecture",
        "branches": [
            {
                "topic": "Frontend Layer",
                "question": "How is frontend structured?",
                "subtopics": [
                    {"name": "React Flow", "children": []}
                ],
            },
            {
                "title": "Backend Layer",
                "categories": [
                    {"label": "FastAPI", "children": []}
                ],
            },
        ],
    })
    result = generator._parse_and_validate(alternative_keys, default_title="Default")
    assert result["id"] == "root"
    assert result["label"] == "Document Architecture"
    assert len(result["children"]) == 2
    assert result["children"][0]["label"] == "Frontend Layer"
    assert result["children"][0]["children"][0]["label"] == "React Flow"
    assert result["children"][1]["label"] == "Backend Layer"


def test_parse_and_validate_unwraps_top_level_dictionary():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    wrapped = json.dumps({
        "mindmap": {
            "id": "root",
            "label": "Wrapped MindMap",
            "query": "Summarize",
            "children": [
                {"id": "c1", "label": "Child 1", "query": "Q1", "children": []}
            ],
        }
    })
    result = generator._parse_and_validate(wrapped, default_title="Default")
    assert result["id"] == "root"
    assert result["label"] == "Wrapped MindMap"
    assert len(result["children"]) == 1


def test_openrouter_error_propagates_as_mindmap_generation_error():
    from app.services.openrouter import OpenRouterGenerationError

    generator = MindMapGenerator.__new__(MindMapGenerator)
    mock_openrouter = MagicMock()
    mock_openrouter.generate.side_effect = OpenRouterGenerationError("OpenRouter service overloaded", status_code=503)
    generator.openrouter_generator = mock_openrouter

    with pytest.raises(MindMapGenerationError) as exc_info:
        generator.generate(["Some content chunks"], "Test Doc", uuid.uuid4())
    assert exc_info.value.status_code == 503
    assert "OpenRouter service overloaded" in str(exc_info.value)


def test_openrouter_passes_response_format_json_object():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    mock_openrouter = MagicMock()
    mock_openrouter.generate.return_value = json.dumps({
        "id": "root",
        "label": "OpenRouter JSON",
        "query": "Summarize",
        "children": [
            {"id": "n1", "label": "Branch A", "query": "QA", "children": []}
        ],
    })
    generator.openrouter_generator = mock_openrouter

    result = generator._generate_with_openrouter("Doc Title", "Doc text", uuid.uuid4())
    assert result["label"] == "OpenRouter JSON"
    assert len(result["children"]) == 1
    mock_openrouter.generate.assert_called_once()
    kwargs = mock_openrouter.generate.call_args.kwargs
    assert kwargs.get("response_format") == {"type": "json_object"}


def test_normalize_node_deduplicates_duplicate_sibling_labels():
    generator = MindMapGenerator.__new__(MindMapGenerator)
    tree_with_duplicates = {
        "id": "root",
        "label": "Artificial Intelligence",
        "children": [
            {
                "id": "sub-1",
                "label": "Definitions and Core Approaches",
                "children": [],
            },
            {
                "id": "sub-2",
                "label": "  definitions and core approaches  ",
                "children": [],
            },
            {
                "id": "sub-3",
                "label": "State of the Art",
                "children": [],
            },
        ],
    }

    result = generator._normalize_node(tree_with_duplicates, seen_ids=set(), default_title="Artificial Intelligence")
    assert len(result["children"]) == 2
    assert result["children"][0]["label"] == "Definitions and Core Approaches"
    assert result["children"][1]["label"] == "State of the Art"


def test_mindmap_generate_request_schema():
    from app.models.schemas import MindMapGenerateRequest

    req_default = MindMapGenerateRequest()
    assert req_default.force is False
    assert req_default.force_regenerate is False
    assert req_default.refresh is False

    req_custom = MindMapGenerateRequest(force=True, force_regenerate=True, refresh=True)
    assert req_custom.force is True
    assert req_custom.force_regenerate is True
    assert req_custom.refresh is True


def test_router_generate_document_mindmap_force_and_cache(monkeypatch):
    from app.routers.mindmap import generate_document_mindmap, get_document_mindmap
    from app.models.entities import Document, DocumentMindMap, User
    from app.models.schemas import MindMapGenerateRequest
    from fastapi import HTTPException

    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    test_user = User(id=user_id, email="test@example.com")
    indexed_doc = Document(
        id=doc_id,
        workspace_id=workspace_id,
        user_id=user_id,
        file_name="test.pdf",
        status="indexed",
    )

    cached_mindmap = DocumentMindMap(
        id=uuid.uuid4(),
        document_id=doc_id,
        workspace_id=workspace_id,
        user_id=user_id,
        tree_data={
            "id": "root",
            "label": "Cached Tree",
            "children": [{"id": "c1", "label": "Branch 1", "children": []}],
        },
    )

    mock_db = MagicMock()

    # GET endpoint: returns cached mind map
    mock_db.scalar.return_value = cached_mindmap
    monkeypatch.setattr("app.routers.mindmap.owned_document", lambda db, u_id, w_id, d_id: indexed_doc)
    res_get = get_document_mindmap(workspace_id, doc_id, db=mock_db, user=test_user)
    assert res_get == cached_mindmap

    # GET endpoint: raises 404 if no mind map
    mock_db.scalar.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        get_document_mindmap(workspace_id, doc_id, db=mock_db, user=test_user)
    assert exc_info.value.status_code == 404

    # POST endpoint: without force/refresh returns cached mindmap
    mock_db.scalar.return_value = cached_mindmap
    res_cached = generate_document_mindmap(
        workspace_id,
        doc_id,
        refresh=False,
        force=False,
        body=None,
        db=mock_db,
        user=test_user,
    )
    assert res_cached == cached_mindmap

    # POST endpoint: with force=True bypasses cache and updates existing
    mock_generator = MagicMock()
    fresh_tree = {
        "id": "root",
        "label": "Fresh Regenerated Tree",
        "children": [{"id": "fresh-1", "label": "Fresh Branch", "children": []}],
    }
    mock_generator.generate.return_value = fresh_tree
    monkeypatch.setattr("app.routers.mindmap.MindMapGenerator", lambda: mock_generator)
    mock_db.scalars.return_value = ["chunk 1 text"]

    res_forced = generate_document_mindmap(
        workspace_id,
        doc_id,
        refresh=False,
        force=True,
        body=None,
        db=mock_db,
        user=test_user,
    )
    assert res_forced.tree_data == fresh_tree
    mock_db.commit.assert_called()

    # POST endpoint: with body.force_regenerate=True also bypasses cache
    mock_db.commit.reset_mock()
    res_body_forced = generate_document_mindmap(
        workspace_id,
        doc_id,
        refresh=False,
        force=False,
        body=MindMapGenerateRequest(force_regenerate=True),
        db=mock_db,
        user=test_user,
    )
    assert res_body_forced.tree_data == fresh_tree
    mock_db.commit.assert_called()

