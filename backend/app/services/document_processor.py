import os
import logging
import time
import uuid
from pathlib import Path
from typing import List, Tuple
from datetime import datetime
from app.services.citation_pipeline import chunk_pages as sentence_chunk_pages

logger = logging.getLogger(__name__)

# PDF Extraction
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("Warning: PyMuPDF (fitz) not found. Please install pymupdf.")
    # Fallback to PyPDF2 if needed, but we really want fitz
    try:
        import PyPDF2
        PYPDF2_AVAILABLE = True
    except ImportError:
        PYPDF2_AVAILABLE = False

# Word Extraction
import docx

# OpenAI & Embeddings
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Vector DB
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

class DocumentProcessor:
    def __init__(self):
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB is required. Install it with: pip install chromadb")
        
        # Initialize ChromaDB
        try:
            self.client = chromadb.PersistentClient(path="./chroma_db")
        except AttributeError:
             from chromadb.config import Settings
             self.client = chromadb.Client(Settings(
                 chroma_db_impl="duckdb+parquet",
                 persist_directory="./chroma_db"
             ))
             
        self.collection = self.client.get_or_create_collection(name="documents")
        self._zero_embedding_warning_logged = False
        
        # Initialize OpenAI or Fallback
        self.openai_client = None
        if OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = OpenAI(api_key=api_key, timeout=20.0, max_retries=0)

        self.gemini_embedding_client = None
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if GEMINI_AVAILABLE and google_api_key:
            self.gemini_embedding_client = genai.Client(
                api_key=google_api_key,
                http_options=genai_types.HttpOptions(
                    timeout=30_000,
                    retry_options=genai_types.HttpRetryOptions(attempts=1),
                ),
            )
        
        self.embedding_model = None
        if not self.openai_client:
            try:
                from sentence_transformers import SentenceTransformer
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            except ImportError:
                print("Warning: No local embedding model available.")

    def _embedding_dimensions(self) -> int:
        """Keep new vectors compatible with the existing Chroma collection."""
        try:
            existing = self.collection.get(limit=1, include=["embeddings"])
            vectors = existing.get("embeddings")
            if vectors is not None and len(vectors):
                return len(vectors[0])
        except Exception as error:
            logger.warning("embedding.dimension_lookup_failed error_type=%s", type(error).__name__)
        return 1536

    def get_embeddings(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        """Generate compatible embeddings using OpenAI, Gemini, then local fallback."""
        if not texts:
            return []
        normalized_texts = [text.replace("\n", " ") for text in texts]

        if self.openai_client:
            embedding_started = time.perf_counter()
            try:
                response = self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=normalized_texts,
                )
                logger.info(
                    "embedding.openai_completed duration_ms=%d batch_size=%d dimensions=%d",
                    round((time.perf_counter() - embedding_started) * 1000),
                    len(response.data),
                    len(response.data[0].embedding),
                )
                return [item.embedding for item in response.data]
            except Exception as e:
                status_code = getattr(e, "status_code", None)
                if status_code == 401:
                    logger.error(
                        "openai.embedding_auth_failed status_code=401; disabling this embedding client"
                    )
                else:
                    logger.warning(
                        "openai.embedding_failed status_code=%s error_type=%s; disabling this embedding client",
                        status_code,
                        type(e).__name__,
                    )
                # Repeated embedding attempts against a rejected or unreachable provider
                # otherwise add up across every retrieval fallback and can stall chat.
                self.openai_client = None

        if self.gemini_embedding_client:
            embedding_started = time.perf_counter()
            try:
                response = self.gemini_embedding_client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=normalized_texts,
                    config=genai_types.EmbedContentConfig(
                        output_dimensionality=self._embedding_dimensions(),
                        task_type=task_type,
                    ),
                )
                vectors = [embedding.values for embedding in response.embeddings]
                logger.info(
                    "embedding.gemini_completed duration_ms=%d batch_size=%d dimensions=%d task_type=%s",
                    round((time.perf_counter() - embedding_started) * 1000),
                    len(vectors),
                    len(vectors[0]) if vectors else 0,
                    task_type,
                )
                if len(vectors) == len(normalized_texts):
                    return vectors
                raise RuntimeError("Gemini returned an unexpected number of embeddings.")
            except Exception as error:
                logger.exception(
                    "embedding.gemini_failed batch_size=%d error_type=%s",
                    len(normalized_texts),
                    type(error).__name__,
                )

        if self.embedding_model:
            return [vector.tolist() for vector in self.embedding_model.encode(normalized_texts)]

        if not self._zero_embedding_warning_logged:
            logger.error("embedding.no_provider_available returning_zero_vectors=true")
            self._zero_embedding_warning_logged = True
        dimensions = self._embedding_dimensions()
        return [[0.0] * dimensions for _ in normalized_texts]

    def get_embedding(self, text: str, task_type: str = "RETRIEVAL_QUERY") -> List[float]:
        return self.get_embeddings([text], task_type=task_type)[0]

    def repair_zero_embeddings(self, document_id: str) -> int:
        """Re-embed legacy document chunks that were stored as zero vectors."""
        if not self.gemini_embedding_client or not document_id:
            return 0
        try:
            records = self.collection.get(
                where={"document_id": document_id},
                include=["documents", "embeddings"],
            )
            documents = records.get("documents") or []
            embeddings = records.get("embeddings")
            ids = records.get("ids") or []
            if not documents or embeddings is None or len(ids) != len(documents):
                return 0

            zero_indices = [
                index for index, vector in enumerate(embeddings)
                if vector is None or not any(value != 0 for value in vector)
            ]
            if not zero_indices:
                return 0

            logger.info(
                "embedding.repair_started document_id=%s zero_vector_chunks=%d",
                document_id,
                len(zero_indices),
            )
            repair_started = time.perf_counter()
            for offset in range(0, len(zero_indices), 32):
                batch_indices = zero_indices[offset:offset + 32]
                vectors = self.get_embeddings(
                    [documents[index] for index in batch_indices],
                    task_type="RETRIEVAL_DOCUMENT",
                )
                self.collection.update(
                    ids=[ids[index] for index in batch_indices],
                    embeddings=vectors,
                )
            logger.info(
                "embedding.repair_completed document_id=%s repaired_chunks=%d duration_ms=%d",
                document_id,
                len(zero_indices),
                round((time.perf_counter() - repair_started) * 1000),
            )
            return len(zero_indices)
        except Exception as error:
            logger.exception(
                "embedding.repair_failed document_id=%s error_type=%s",
                document_id,
                type(error).__name__,
            )
            return 0

    def extract_text_from_pdf(self, file_path: Path) -> Tuple[str, List[Tuple[int, str]]]:
        """Extract text using PyMuPDF (fitz) - superior quality"""
        full_text = ""
        pages_data = []
        
        if PYMUPDF_AVAILABLE:
            try:
                doc = fitz.open(file_path)
                for page_num, page in enumerate(doc, start=1):
                    # "text" block mode preserves paragraphs better
                    page_text = page.get_text("text") 
                    if page_text.strip():
                        # Clean up headers/footers roughly (simple heuristic)
                        lines = page_text.split('\n')
                        # Remove lonely page numbers
                        lines = [l for l in lines if not (l.strip().isdigit() and len(l.strip()) < 4)]
                        cleaned_page_text = '\n'.join(lines)
                        
                        full_text += cleaned_page_text + "\n\n"
                        pages_data.append((page_num, cleaned_page_text))
                return full_text, pages_data
            except Exception as e:
                print(f"PyMuPDF error: {e}. Falling back to PyPDF2 if available.")
        
        # Fallback
        if PYPDF2_AVAILABLE:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for i, page in enumerate(reader.pages):
                    t = page.extract_text()
                    full_text += t + "\n"
                    pages_data.append((i+1, t))
            return full_text, pages_data
            
        raise ValueError("No PDF extraction library available.")

    def extract_text_from_docx(self, file_path: Path) -> str:
        doc = docx.Document(file_path)
        return "\n\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())

    def recursive_chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 2) -> List[str]:
        """Compatibility wrapper around the shared sentence-boundary chunker."""
        del overlap  # Legacy callers passed a character count; overlap is now sentence based.
        return [content for _, content in sentence_chunk_pages([(1, text)], size=chunk_size)]

    def process_document(self, file_path: Path, filename: str) -> str:
        document_id = str(uuid.uuid4())
        
        pages_data = None
        text = ""
        
        if filename.endswith('.pdf'):
            text, pages_data = self.extract_text_from_pdf(file_path)
        elif filename.endswith(('.doc', '.docx')):
            text = self.extract_text_from_docx(file_path)
            pages_data = [(1, text)]
            
        if not text.strip():
            raise ValueError("Empty document")
            
        # Store pages for page-based queries (e.g. "what is on page 5")
        if not hasattr(self, '_document_pages'): self._document_pages = {}
        self._document_pages[document_id] = pages_data
        
        # Split each extracted page independently so citation page metadata stays exact.
        page_chunks = sentence_chunk_pages(pages_data or [(1, text)], size=800, overlap_sentences=2)
        chunks = [content for _, content in page_chunks]
        
        # Prepare for DB
        embeddings = self.get_embeddings(chunks, task_type="RETRIEVAL_DOCUMENT")
        ids = []
        metadatas = []
        docs = []
        
        for i, (page_num, chunk) in enumerate(page_chunks):
            
            chunk_id = f"{document_id}_{i}"
            
            ids.append(chunk_id)
            metadatas.append({
                "document_id": document_id,
                "filename": filename,
                "chunk_index": i,
                "page_number": page_num,
                "upload_date": datetime.now().isoformat()
            })
            docs.append(chunk)
            
        self.collection.add(
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas,
            documents=docs
        )
        
        return document_id

    def search_documents(self, query: str, n_results: int = 5, document_id: str = None) -> List[Tuple[str, float]]:
        """Search and return (text, distance)
        document_id: If provided, only search within this specific document
        """
        try:
            q_emb = self.get_embedding(query, task_type="RETRIEVAL_QUERY")
            
            # Build query with optional document_id filter
            query_params = {
                "query_embeddings": [q_emb],
                "n_results": n_results
            }
            
            # Add document_id filter if provided
            # ChromaDB where filter syntax - try both formats for compatibility
            if document_id:
                try:
                    # Try the $eq operator syntax (newer ChromaDB versions)
                    query_params["where"] = {"document_id": {"$eq": document_id}}
                except:
                    # Fallback to simple equality (older ChromaDB versions)
                    query_params["where"] = {"document_id": document_id}
            
            search_started = time.perf_counter()
            results = self.collection.query(**query_params)
            logger.info(
                "vector_search.completed duration_ms=%d requested_results=%d",
                round((time.perf_counter() - search_started) * 1000),
                n_results,
            )
            
            if not results['documents']:
                return []
                
            docs = results['documents'][0]
            dists = results['distances'][0] if 'distances' in results else [0.0]*len(docs)
            
            return list(zip(docs, dists))
            
        except Exception as e:
            logger.exception("vector_search.failed error_type=%s", type(e).__name__)
            return []

# Singleton
document_processor = DocumentProcessor()
def get_document_processor():
    return document_processor
