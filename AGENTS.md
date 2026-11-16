# AI Agent Guidelines - Document Chatbot Workspace Platform

## Mandatory Repository Context Synchronization Rule

Whenever you make any changes to this repository, you MUST keep [`REPO_CONTEXT.md`](file:///home/shripad/Desktop/miniproject/ai-document-chatbot/REPO_CONTEXT.md) strictly synchronized with your changes.
This is a mandatory requirement for all agents, contributors, and automated workflows.

### What Must Be Updated in `REPO_CONTEXT.md`
1. **Architecture & Features**:
   If adding or refactoring services, models, pipelines, or background workers, update Section 1 (Executive Summary) and the Mermaid architecture diagram.
2. **Directory & File Inventory**:
   If creating, deleting, or renaming files or folders, update Section 2 (Directory Tree and File Inventory) with the accurate file paths and descriptions.
3. **Dependencies**:
   If modifying `requirements.txt` or `package.json`, update Section 3 (Technology Stack and Dependencies).
4. **Database & Migrations**:
   If modifying SQLAlchemy models in `entities.py` or adding Alembic migration scripts, update Section 4 (Database Schema and Entity Relationships) including the Mermaid ER diagram and table definitions.
5. **API Endpoints**:
   If adding, modifying, or removing FastAPI endpoints, update Section 9 (API Specification and Endpoint Reference).
6. **Frontend Components & UI**:
   If adding or modifying React components, CSS token architecture, or layout hooks, update Section 10 (Frontend Architecture).
7. **Active vs Legacy Mapping**:
   If deprecating or replacing old modules, update Section 11 (Legacy Code vs Active Code Map).
8. **Configuration & Environment**:
   If introducing or modifying environment variables in `config.py` or `.env.example`, update Section 12 (Configuration and Environment Variables).
9. **Tests and Verification**:
   If introducing new test suites or evaluation scripts, update Section 13 (Local Development, Testing, and Benchmarking).

## Markdown Formatting Rules
- When writing or editing Markdown files, always place each full sentence on its own physical line.
- Never use the em dash character.
  Use a plain dash "-" instead.
