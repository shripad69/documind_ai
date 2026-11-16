"""Service to generate hierarchical mind maps from document content directly using OpenRouter."""

import json
import logging
import re
from typing import Any
from uuid import UUID

from app.config import settings
from app.models.schemas import MindMapNodeSchema
from app.services.openrouter import OpenRouterAnswerGenerator, OpenRouterGenerationError

logger = logging.getLogger(__name__)


class MindMapGenerationError(Exception):
    """Raised when mind map generation or parsing fails."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class MindMapGenerator:
    def __init__(self):
        self.openrouter_generator = OpenRouterAnswerGenerator()

    @staticmethod
    def prepare_document_text(chunks: list[str], max_chars: int = 24000) -> str:
        """Combine document chunks into a representative text sample within token limits."""
        if not chunks:
            return ""

        total_length = sum(len(chunk) for chunk in chunks)
        if total_length <= max_chars:
            return "\n\n".join(chunks)

        if len(chunks) <= 5:
            combined = "\n\n".join(chunks)
            return combined[:max_chars]

        intro = chunks[:3]
        outro = chunks[-2:]
        middle_candidates = chunks[3:-2]

        budget = max_chars - sum(len(chunk) for chunk in intro) - sum(len(chunk) for chunk in outro) - 500
        sampled_middle: list[str] = []

        if budget > 0 and middle_candidates:
            step = max(1, len(middle_candidates) // max(1, budget // 800))
            for i in range(0, len(middle_candidates), step):
                chunk = middle_candidates[i]
                if sum(len(c) for c in sampled_middle) + len(chunk) <= budget:
                    sampled_middle.append(chunk)
                else:
                    break

        all_parts = intro + (["[... content omitted for brevity ...]"] if sampled_middle else []) + sampled_middle + ["[... content omitted for brevity ...]"] + outro
        return "\n\n".join(all_parts)

    def generate(self, chunks: list[str], document_name: str, document_id: UUID | str) -> dict[str, Any]:
        """Generate a recursive mind map tree directly via OpenRouter."""
        if not chunks:
            raise MindMapGenerationError("The document has no readable text content to generate a mind map.", status_code=400)

        document_text = self.prepare_document_text(chunks)
        if not document_text.strip():
            raise MindMapGenerationError("The document content is empty.", status_code=400)

        return self._generate_with_openrouter(document_name, document_text, document_id)

    def _generate_with_openrouter(self, document_name: str, document_text: str, document_id: UUID | str) -> dict[str, Any]:
        system_prompt = (
            "You are an expert knowledge architect. Analyze the document and output a compact, hierarchical "
            "mind map tree in valid JSON format matching this structure:\n"
            "{\n"
            '  "id": "root",\n'
            f'  "label": "{document_name[:40]}",\n'
            f'  "query": "Summarize {document_name[:40]}",\n'
            '  "children": [\n'
            '    {\n'
            '      "id": "node-1",\n'
            '      "label": "Theme 1",\n'
            '      "query": "Explain Theme 1",\n'
            '      "children": [\n'
            '        {\n'
            '          "id": "node-1-1",\n'
            '          "label": "Concept 1.1",\n'
            '          "query": "Detail Concept 1.1",\n'
            '          "children": []\n'
            '        }\n'
            '      ]\n'
            '    }\n'
            '  ]\n'
            "}\n\n"
            "REQUIREMENTS:\n"
            "- Root node (Level 0): 'id': 'root', 'label': Document Topic (2-6 words), 'query': 'Summarize [Topic]'.\n"
            "- Level 1 branches: 3 to 5 core categories.\n"
            "- Level 2 sub-nodes: 2 to 3 concepts per category.\n"
            "- Level 3 points: 1 to 2 details under key concepts.\n"
            "- Every node must have 'id', 'label', 'query', and 'children' list.\n"
            "- CRITICAL: The root node MUST contain at least 3 child branch nodes in its 'children' array.\n"
            "- Keep labels under 6 words.\n"
            "- Output ONLY valid raw JSON starting with '{' and ending with '}'. Do NOT output <think> tags, markdown fences, or commentary."
        )

        user_content = (
            f"Document Title: {document_name}\n\n"
            f"Document Text Content:\n{document_text}\n\n"
            "Generate JSON mind map tree with at least 3 child branches:"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        correlation_id = f"mindmap-{document_id}"
        try:
            raw_output = self.openrouter_generator.generate(
                messages,
                correlation_id=correlation_id,
                max_tokens=4096,
                response_format={"type": "json_object"},
                reasoning_effort="none",  # Instruct reasoning models not to spend token budget on thinking
            )
        except OpenRouterGenerationError as error:
            logger.warning("mindmap.openrouter_failed document_id=%s detail=%s", document_id, str(error))
            raise MindMapGenerationError(str(error), status_code=error.status_code or 502) from error

        return self._parse_and_validate(raw_output, document_name)

    def _parse_and_validate(self, raw_output: str, default_title: str) -> dict[str, Any]:
        """Extract, repair if truncated, sanitize, and validate the JSON mind map tree."""
        if not raw_output or not raw_output.strip():
            logger.error("mindmap.empty_llm_output default_title=%s", default_title)
            raise MindMapGenerationError(
                "The AI model returned an empty response. Please retry.",
                status_code=502,
            )

        cleaned = raw_output.strip()

        # 1. Strip reasoning blocks: <think>...</think>
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE).strip()
        # Handle unclosed <think> tag if text before { was inside a thinking block
        cleaned = re.sub(r"^<think>[\s\S]*?(?=\{)", "", cleaned, flags=re.IGNORECASE).strip()

        # 2. Strip markdown fences if present
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, flags=re.IGNORECASE)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        else:
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        # 3. Direct load
        data = None
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try regex extraction of outermost balanced {...}
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end > start:
                candidate = cleaned[start : end + 1]
                try:
                    data = json.loads(candidate)
                except json.JSONDecodeError:
                    pass

        # 4. If still unparsed, attempt truncated JSON repair
        if not isinstance(data, dict):
            repaired = self._repair_truncated_json(cleaned)
            if repaired:
                try:
                    data = json.loads(repaired)
                except json.JSONDecodeError:
                    pass

        # 5. Check if valid dict parsed
        if not isinstance(data, dict):
            logger.error("mindmap.unparseable_json output_sample=%s", raw_output[:500])
            raise MindMapGenerationError(
                "The AI model returned an unparseable mind map response. Please retry.",
                status_code=502,
            )

        # 6. Unwrap top-level dictionary wrappers if present (e.g. {"mindmap": {...}}, {"tree": {...}})
        for wrapper_key in ("mindmap", "mind_map", "tree", "root_node"):
            if wrapper_key in data and isinstance(data[wrapper_key], dict):
                data = data[wrapper_key]
                break

        # 7. Normalize node fields recursively
        seen_ids: set[str] = set()
        normalized = self._normalize_node(data, seen_ids, default_title=default_title, path="root")

        # 8. Strict validation: root MUST have non-empty children (explicitly reject 1-node fallback)
        root_children = normalized.get("children")
        if not root_children or not isinstance(root_children, list) or len(root_children) == 0:
            logger.error(
                "mindmap.empty_children_rejected default_title=%s raw_output_sample=%s",
                default_title,
                raw_output[:500],
            )
            raise MindMapGenerationError(
                "The AI model generated an empty mind map with zero branches. Please retry.",
                status_code=502,
            )

        # 9. Pydantic schema validation
        try:
            validated = MindMapNodeSchema.model_validate(normalized)
            return validated.model_dump()
        except Exception as error:
            logger.error("mindmap.schema_validation_failed error=%s raw_output_sample=%s", error, raw_output[:500])
            raise MindMapGenerationError(
                "Mind map schema validation failed. Please retry.",
                status_code=502,
            ) from error

    @staticmethod
    def _repair_truncated_json(text: str) -> str | None:
        """Heuristic repair for JSON truncated mid-output."""
        # Find first opening brace
        start = text.find("{")
        if start == -1:
            return None
        truncated = text[start:].strip()

        # Close unclosed string if quote count is odd
        in_string = False
        escape = False
        stack = []
        for char in truncated:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char in "{[":
                    stack.append("}" if char == "{" else "]")
                elif char in "}]":
                    if stack and stack[-1] == char:
                        stack.pop()

        repaired = truncated
        if in_string:
            repaired += '"'

        # Remove trailing comma before closing
        repaired = re.sub(r",\s*$", "", repaired)

        # Close any open structures in reverse order
        while stack:
            repaired += stack.pop()

        return repaired

    def _normalize_node(
        self,
        node: dict[str, Any],
        seen_ids: set[str],
        default_title: str,
        path: str = "root",
    ) -> dict[str, Any]:
        """Ensure all required fields exist, labels are trimmed, and IDs are unique."""
        raw_id = str(node.get("id") or path).strip()
        if not raw_id or raw_id in seen_ids:
            raw_id = f"{path}-{len(seen_ids) + 1}"
        seen_ids.add(raw_id)

        # Flexible label extraction (check label, title, topic, name)
        raw_label = str(
            node.get("label")
            or node.get("title")
            or node.get("topic")
            or node.get("name")
            or (default_title if path == "root" else "Concept")
        ).strip()
        if not raw_label:
            raw_label = default_title if path == "root" else "Concept"

        raw_query = str(node.get("query") or node.get("question") or "").strip()
        if not raw_query:
            raw_query = f"Explain {raw_label} in detail based on the document."

        # Flexible children extraction (check children, branches, subtopics, nodes, categories, sub_nodes, sections)
        raw_children = (
            node.get("children")
            or node.get("branches")
            or node.get("subtopics")
            or node.get("nodes")
            or node.get("categories")
            or node.get("sub_nodes")
            or node.get("sections")
        )
        if isinstance(raw_children, dict):
            raw_children = list(raw_children.values())

        children: list[dict[str, Any]] = []
        if isinstance(raw_children, list):
            seen_child_labels: set[str] = set()
            for index, child in enumerate(raw_children, start=1):
                if isinstance(child, dict):
                    child_label = str(
                        child.get("label")
                        or child.get("title")
                        or child.get("topic")
                        or child.get("name")
                        or ""
                    ).strip()
                    norm_label = child_label.lower()
                    if norm_label and norm_label in seen_child_labels:
                        continue
                    if norm_label:
                        seen_child_labels.add(norm_label)

                    child_path = f"{raw_id}-{index}"
                    children.append(self._normalize_node(child, seen_ids, default_title, path=child_path))
                elif isinstance(child, str) and child.strip():
                    child_text = child.strip()
                    norm_label = child_text.lower()
                    if norm_label in seen_child_labels:
                        continue
                    seen_child_labels.add(norm_label)

                    child_path = f"{raw_id}-{index}"
                    children.append({
                        "id": child_path,
                        "label": child_text[:80],
                        "query": f"Explain {child_text} in detail based on the document.",
                        "children": [],
                    })

        return {
            "id": raw_id,
            "label": raw_label[:80],
            "query": raw_query[:300],
            "children": children,
        }
