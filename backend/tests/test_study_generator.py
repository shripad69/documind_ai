"""Tests for stateless study set generation and the workspace study endpoint."""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.models.entities import Document, User, Workspace
from app.models.schemas import StudyGenerateRequest, StudySetOut
from app.services.study_generator import StudyGenerationError, StudyGenerator


class FakeOpenRouter:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def generate(self, messages, correlation_id, **kwargs):
        self.calls.append(
            {"messages": messages, "correlation_id": correlation_id, "kwargs": kwargs}
        )
        return self.output


def make_document(document_id, name, chunk_contents):
    return {
        "document_id": document_id,
        "document_name": name,
        "chunks": [
            {
                "chunk_id": f"{document_id}-{index}",
                "chunk_index": index,
                "page_number": index + 1,
                "content": content,
            }
            for index, content in enumerate(chunk_contents)
        ],
    }


def padded(label, index, repeats=40):
    return f"{label} section {index}: " + (f"{label} findings " * repeats)


def test_registry_samples_first_middle_and_last_chunks_across_documents():
    alpha = make_document(
        "alpha",
        "Alpha.pdf",
        [padded("Alpha", index) for index in range(30)],
    )
    beta = make_document(
        "beta",
        "Beta.pdf",
        [padded("Beta", index) for index in range(30)],
    )

    registry = StudyGenerator.build_citation_registry([alpha, beta])
    contents = "\n".join(chunk["content"] for chunk in registry.values())

    assert "Alpha section 0:" in contents
    assert "Alpha section 29:" in contents
    assert "Beta section 0:" in contents
    assert "Beta section 29:" in contents
    assert len(contents) <= 22_000
    assert {chunk["document_name"] for chunk in registry.values()} == {
        "Alpha.pdf",
        "Beta.pdf",
    }
    assert list(registry) == [f"chunk_{index}" for index in range(1, len(registry) + 1)]


def test_generate_repairs_fenced_truncated_json_and_resolves_citations():
    output = (
        "<think>hidden plan</think>```json\n"
        '{"flashcards": [{"front": "What powers the rover?", '
        '"back": "Solar panels provide power [chunk_2]."}, '
        '{"front": "Incomplete card", "back": "cut'
    )
    fake = FakeOpenRouter(output)
    generator = StudyGenerator(fake)
    document = make_document(
        "doc-1",
        "Rover.pdf",
        ["Solar panels provide power.", "The rover weighs 900 kg."],
    )

    result = generator.generate(
        [document],
        mode="flashcards",
        count=5,
        difficulty="medium",
        correlation_id="test",
    )

    assert result.mode == "flashcards"
    assert result.difficulty == "medium"
    assert len(result.flashcards) == 1
    card = result.flashcards[0]
    assert card.front == "What powers the rover?"
    assert card.back == "Solar panels provide power [chunk_1]."
    assert card.source_references[0]["file_name"] == "Rover.pdf"
    assert card.source_references[0]["page_number"] == 2
    assert fake.calls[0]["kwargs"]["response_format"] == {"type": "json_object"}
    assert fake.calls[0]["kwargs"]["reasoning_effort"] == "none"


def test_quiz_validation_rejects_bad_indexes_and_option_counts():
    output = json.dumps(
        {
            "questions": [
                {
                    "question": "Which instrument captured the image?",
                    "options": ["A", "B", "C", "D"],
                    "correct_index": 2,
                    "explanation": "The camera is described here [chunk_1].",
                },
                {
                    "question": "Bad index",
                    "options": ["A", "B", "C", "D"],
                    "correct_index": 7,
                    "explanation": "Bad [chunk_1].",
                },
                {
                    "question": "Three options",
                    "options": ["A", "B", "C"],
                    "correct_index": 0,
                    "explanation": "Bad [chunk_1].",
                },
            ]
        }
    )
    generator = StudyGenerator(FakeOpenRouter(output))
    document = make_document("doc-2", "Camera.pdf", ["The camera captured the image."])

    result = generator.generate([document], mode="quiz", count=5)

    assert result.mode == "quiz"
    assert len(result.questions) == 1
    assert result.questions[0].correct_index == 2
    assert result.questions[0].source_references[0]["citation_id"] == "chunk_1"


def test_generate_caps_items_at_requested_count():
    cards = [
        {"front": f"Card {index}", "back": "A documented fact [chunk_1]."}
        for index in range(4)
    ]
    generator = StudyGenerator(FakeOpenRouter(json.dumps({"flashcards": cards})))
    document = make_document("doc-3", "Facts.pdf", ["Facts are documented here."])

    result = generator.generate([document], mode="flashcards", count=2)

    assert len(result.flashcards) == 2


def test_generate_requires_verifiable_citations():
    generator = StudyGenerator(
        FakeOpenRouter('{"flashcards": [{"front": "Q", "back": "No source."}]}')
    )
    document = make_document("doc-4", "Empty.pdf", ["Some indexed text."])

    with pytest.raises(StudyGenerationError) as exc_info:
        generator.generate([document], mode="flashcards")

    assert exc_info.value.status_code == 502


USER_ID = uuid.uuid4()
WORKSPACE_ID = uuid.uuid4()


def study_user():
    return User(id=USER_ID, email="study@example.com")


def study_workspace():
    return Workspace(id=WORKSPACE_ID, user_id=USER_ID, title="Study")


def study_document(status):
    return Document(
        id=uuid.uuid4(),
        workspace_id=WORKSPACE_ID,
        user_id=USER_ID,
        file_name="ai.pdf",
        file_path="/tmp/ai.pdf",
        status=status,
    )


def test_study_endpoint_returns_409_for_processing_targets(monkeypatch):
    from app.routers import workspaces as router_module

    processing = study_document("processing")
    db = MagicMock()
    db.scalars.return_value = [processing]
    monkeypatch.setattr(router_module, "owned_workspace", lambda *args, **kwargs: study_workspace())

    with pytest.raises(HTTPException) as exc_info:
        router_module.generate_study_set(
            WORKSPACE_ID,
            StudyGenerateRequest(mode="flashcards", document_ids=[processing.id]),
            db=db,
            user=study_user(),
        )

    assert exc_info.value.status_code == 409


def test_study_endpoint_returns_400_when_no_documents_are_indexed(monkeypatch):
    from app.routers import workspaces as router_module

    failed = study_document("failed")
    db = MagicMock()
    db.scalars.return_value = [failed]
    monkeypatch.setattr(router_module, "owned_workspace", lambda *args, **kwargs: study_workspace())

    with pytest.raises(HTTPException) as exc_info:
        router_module.generate_study_set(
            WORKSPACE_ID,
            StudyGenerateRequest(mode="quiz"),
            db=db,
            user=study_user(),
        )

    assert exc_info.value.status_code == 400


def test_study_endpoint_returns_404_for_foreign_document_id(monkeypatch):
    from app.routers import workspaces as router_module

    indexed = study_document("indexed")
    db = MagicMock()
    db.scalars.return_value = [indexed]
    monkeypatch.setattr(router_module, "owned_workspace", lambda *args, **kwargs: study_workspace())

    with pytest.raises(HTTPException) as exc_info:
        router_module.generate_study_set(
            WORKSPACE_ID,
            StudyGenerateRequest(mode="flashcards", document_ids=[uuid.uuid4()]),
            db=db,
            user=study_user(),
        )

    assert exc_info.value.status_code == 404


def test_study_endpoint_generates_from_indexed_chunks(monkeypatch):
    from app.routers import workspaces as router_module

    indexed = study_document("indexed")
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        document_id=indexed.id,
        chunk_index=0,
        page_number=4,
        content="Artificial intelligence simulates human intelligence.",
    )
    db = MagicMock()
    db.scalars.return_value = [indexed]
    db.execute.return_value.all.return_value = [(chunk, indexed.file_name)]
    expected = StudySetOut(
        mode="flashcards",
        difficulty="medium",
        document_names=[indexed.file_name],
        flashcards=[
            {
                "id": "flashcard-1",
                "front": "What is AI?",
                "back": "Simulation of human intelligence [chunk_1].",
                "source_references": [],
            }
        ],
    )
    fake_generator = MagicMock()
    fake_generator.generate.return_value = expected
    monkeypatch.setattr(router_module, "owned_workspace", lambda *args, **kwargs: study_workspace())
    monkeypatch.setattr(router_module, "StudyGenerator", lambda: fake_generator)

    result = router_module.generate_study_set(
        WORKSPACE_ID,
        StudyGenerateRequest(mode="flashcards", count=5),
        db=db,
        user=study_user(),
    )

    assert result is expected
    documents_payload = fake_generator.generate.call_args.args[0]
    assert documents_payload[0]["document_name"] == "ai.pdf"
    assert documents_payload[0]["chunks"][0]["page_number"] == 4
