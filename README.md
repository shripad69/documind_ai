# Document Chatbot

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-FF6B6B)](https://www.trychroma.com/)
[![OpenRouter](https://img.shields.io/badge/LLM-OpenRouter-6467F2)](https://openrouter.ai/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Full-stack **RAG (Retrieval-Augmented Generation)** chatbot — upload PDF/DOCX documents and chat with their contents.

---

## 📖 About

Document Chatbot is a full-stack **RAG (Retrieval-Augmented Generation)** application that allows users to upload PDF/DOC/DOCX files and ask context-aware questions about their content.

The current workspace app combines **FastAPI**, **PostgreSQL/pgvector**, and **OpenRouter** for isolated semantic retrieval and AI-powered responses, with a **React** frontend for document conversations. Gemini is retained only for document and query embeddings.

## 🏗️ How It Works

```mermaid
flowchart LR
    A[Upload Document<br/>PDF / DOC / DOCX] --> B[Parse Document<br/>PyMuPDF · python-docx]
    B --> C[Semantic Chunking]
    C --> D[Generate Embeddings<br/>OpenAI / Sentence-Transformers]
    D --> E[(ChromaDB<br/>Vector Store)]
    F[User Query] --> G[Vector Retrieval<br/>Top-k similar chunks]
    E --> G
    G --> H[OpenRouter chat completions<br/>Gemma 4 31B free]
    H --> I[AI Response]
```

1. **Document Ingestion** — User uploads a file via the React UI.
2. **Parsing & Chunking** — FastAPI parses the document and splits it into semantic chunks.
3. **Embedding** — Each chunk is embedded (OpenAI API with sentence-transformers fallback) and stored in ChromaDB.
4. **Retrieval** — On each user query, the top-k most relevant chunks are retrieved by vector similarity.
5. **Generation** — Retrieved workspace chunks, recent chat history, and the current question are sent to OpenRouter for a grounded answer with source citations.

## 🖼️ Screenshots

| Document Upload & First Query | Detailed RAG Response with Citations |
|:---:|:---:|
| ![Upload](docs/screenshots/upload.png) | ![Chat](docs/screenshots/chat.png) |
| **Page-Specific Query** | **AI-Generated Quiz from Document** |
| ![Page Query](docs/screenshots/page-query.png) | ![Quiz](docs/screenshots/quiz.png) |

> Answers include source citations (e.g. `(4/34)`, `(31/34)`) that reference the exact page in the uploaded document — making every response verifiable.

## ✨ Features

### 📄 Document Processing
- PDF, DOC, and DOCX upload
- Semantic chunking
- Multi-document indexing
- Page-specific querying (_"what is on page 5?"_)

### 🤖 AI & Retrieval
- ChromaDB vector search
- Context-aware, grounded responses
- OpenRouter-compatible LLM answer generation (default: `google/gemma-4-31b-it:free`)
- Smart query preprocessing
- Hybrid embedding pipeline (OpenAI → Sentence-Transformers fallback)

### ⚛️ Frontend & UX
- ChatGPT-style chat interface
- Conversation history
- Per-document conversation isolation
- Responsive React UI

### 🐳 DevOps
- Dockerized deployment (Docker · docker-compose)
- Nginx reverse proxy configuration
- CI/CD pipeline preparation

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI · Uvicorn · Python 3.10+ |
| **Frontend** | React 18 · Axios · CSS3 |
| **Vector DB** | PostgreSQL · pgvector |
| **LLM** | OpenRouter (default: Gemma 4 31B free) |
| **Embeddings** | Google Gemini `gemini-embedding-001` |
| **Document Parsing** | PyMuPDF (fitz) · python-docx |
| **Deployment** | Docker · docker-compose · Nginx |
| **CI/CD** | Automated build / test / deploy workflow |

## 🚀 Quick Start

The Docker Compose setup starts the API, ingestion worker, PostgreSQL/pgvector, Redis, and frontend together:

```bash
cp backend/.env.example backend/.env
# Set GOOGLE_API_KEY and OPENROUTER_API_KEY in backend/.env
./restart_project.sh
```

Access the app at **http://localhost:8080** and API docs at **http://localhost:8000/docs**. See [CONFIGURATION.md](CONFIGURATION.md) for provider configuration.

## ⚙️ Detailed Setup

### Prerequisites
- Python 3.10+
- Node.js 16+ and npm
- Google AI Studio API key for embeddings ([get one here](https://aistudio.google.com/apikey))
- OpenRouter API key for answer generation ([get one here](https://openrouter.ai/keys))

### Backend

```bash
cd backend
python -m venv venv

# Activate venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS/Linux

pip install -r requirements.txt
```

Create `backend/.env` from `backend/.env.example` and set:

```env
GOOGLE_API_KEY=your-google-api-key-here   # embeddings
OPENROUTER_API_KEY=your-openrouter-api-key-here  # answer generation
# OPENROUTER_MODEL=google/gemma-4-31b-it:free
```

Run the server:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm start
```

### Docker

```bash
docker-compose up --build
```

Includes Dockerized deployment setup, Nginx reverse proxy configuration, and CI/CD workflow preparation.

## 💡 Usage Examples

After uploading a document, try queries like:

- _"What is this document about?"_
- _"Summarize the main points."_
- _"What is on page 5?"_
- _"Create 10 quiz questions about this document."_
- _"What are the key takeaways from chapter 2?"_

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/upload` | Upload and process a document |
| `GET`  | `/api/documents/list` | List processed documents |
| `POST` | `/api/chat/` | Send a chat message |
| `GET`  | `/api/chat/conversation/{id}` | Get conversation history |
| `GET`  | `/api/health` | Health check |

Interactive API docs available at **http://127.0.0.1:8000/docs** (Swagger UI).

## 📝 Notes & Current Limitations

- PostgreSQL/pgvector stores workspaces, documents, chat history, and embeddings; Redis/Celery handle background ingestion.
- The current chat endpoint returns complete responses; it does not stream tokens.
- OpenRouter free endpoints may apply rate limits or become temporarily unavailable. The backend retries transient failures twice with bounded exponential backoff.

## 🐛 Troubleshooting

<details>
<summary><b>Backend issues</b></summary>

- Ensure all Python dependencies are installed (`pip install -r requirements.txt`)
- Check that port 8000 is not in use
- Verify `backend/.env` contains valid `GOOGLE_API_KEY` and `OPENROUTER_API_KEY` values
</details>

<details>
<summary><b>Frontend issues</b></summary>

- Ensure Node.js 16+ and npm are installed
- Try clearing npm cache: `npm cache clean --force`
- Check that port 3000 is not in use
</details>

<details>
<summary><b>Embedding / chat issues</b></summary>

- A valid Gemini key is required for PDF embeddings.
- Make sure the Gemini key is valid for embeddings and the OpenRouter key/model has access to answer generation
</details>

## 🚧 Future Improvements

- Streaming AI responses (Server-Sent Events)
- Hybrid search (BM25 + vector search)
- Document summarization workflows
- Kubernetes deployment manifests
- End-to-end test coverage

## 👤 Author

**Aylin Kars**
Czech Technical University in Prague — FIT
🔗 [GitHub](https://github.com/karsayli)

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
