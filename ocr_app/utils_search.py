import re
import faiss
from django.conf import settings
from sentence_transformers import SentenceTransformer
from archievesystem.models import Document

from collections import Counter
from rapidfuzz import process  # Fast fuzzy matching library

# Initialize FAISS & SBERT with correct embedding size
sbert_model = SentenceTransformer("sentence-transformers/LaBSE")
index = faiss.IndexFlatL2(768)  # Use 768 instead of 384
documents_db = []  # Store document IDs
word_frequency = Counter()  # Dictionary to store word frequency


def index_documents():
    """Indexes all documents using FAISS and SBERT & builds word suggestions."""
    global index, documents_db, word_frequency
    documents = Document.objects.all()

    texts = []
    doc_ids = []
    word_list = []

    for doc in documents:
        if doc.extracted_text:
            texts.append(doc.extracted_text)
            doc_ids.append(doc.id)

            # Extract words and update frequency count
            words = re.findall(r"\b\w+\b", doc.extracted_text.lower())
            word_list.extend(words)

        if doc.file:
            words = re.findall(r"\b\w+\b", doc.file.name.lower())
            word_list.extend(words)

    if not texts:
        return  # Exit if no valid documents

    # Encode documents using LaBSE
    embeddings = sbert_model.encode(texts, convert_to_numpy=True)

    # Ensure embeddings are correctly shaped
    if embeddings.shape[1] != 768:
        embeddings = embeddings.reshape(-1, 768)

    # Reset FAISS index
    index = faiss.IndexFlatL2(768)
    documents_db = doc_ids  # Store document IDs
    index.add(embeddings)

    # Build word frequency for suggestions
    word_frequency = Counter(word_list)


def suggest_documents(query, top_n=5):
    """Suggests similar documents based on query using FAISS similarity search."""
    global index, documents_db

    if index.ntotal == 0:
        index_documents()  # Rebuild FAISS index if empty

    # Encode the query
    query_embedding = sbert_model.encode([query], convert_to_numpy=True)

    # Ensure query shape matches FAISS index
    if query_embedding.shape[1] != 768:
        query_embedding = query_embedding.reshape(-1, 768)

    # Perform FAISS search
    _, indices = index.search(query_embedding, top_n)

    # Retrieve matching documents
    suggested_docs = [Document.objects.get(id=documents_db[i]) for i in indices[0] if i < len(documents_db)]
    return [doc.get_file_url() for doc in suggested_docs]


def search_documents(query):
    """Searches documents by name and content, with spelling correction and suggestions."""
    global index, documents_db

    if index.ntotal == 0:
        index_documents()  # Rebuild FAISS index if empty

    query_lower = query.lower()
    word_pattern = rf"\b{re.escape(query_lower)}\b"

    # Step 1: Check exact matches
    matched_documents = [
        doc for doc in Document.objects.all()
        if (doc.extracted_text and re.search(word_pattern, doc.extracted_text, re.IGNORECASE))
        or (doc.file and re.search(word_pattern, doc.file.name, re.IGNORECASE))
    ]

    # Step 2: If no exact match, suggest similar documents using FAISS
    if not matched_documents:
        return suggest_documents(query, top_n=5)

    # Step 3: Return file URLs of matched documents
    return [doc.get_file_url() for doc in matched_documents]
