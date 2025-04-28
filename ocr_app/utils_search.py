import re
import os
import faiss
from django.conf import settings
from sentence_transformers import SentenceTransformer
from archievesystem.models import Document
from urllib.parse import unquote
from django.core.files.storage import default_storage
from collections import Counter
from rapidfuzz import process, fuzz

# Initialize FAISS & SBERT
sbert_model = SentenceTransformer("sentence-transformers/LaBSE")
index = faiss.IndexFlatL2(768)
documents_db = []  # Store document IDs
word_frequency = Counter()  # For word suggestions

def index_documents():
    """Indexes all documents using FAISS and SBERT."""
    global index, documents_db, word_frequency
    documents = Document.objects.all()

    texts = []
    doc_ids = []
    word_list = []

    for doc in documents:
        # Extract text for indexing
        if doc.extracted_text:
            texts.append(doc.extracted_text)
            doc_ids.append(doc.id)

        # Extract words from extracted text and filename for suggestions
        if doc.extracted_text:
            words = re.findall(r"\b\w+\b", doc.extracted_text.lower())
            word_list.extend(words)
        
        if doc.file:
            # Extract original filename part before the first underscore
            original_name = os.path.basename(doc.file.name).split('_')[0]
            words = re.findall(r"\b\w+\b", original_name.lower())
            word_list.extend(words)

    if not texts:
        return  # No documents to index

    # Encode documents
    embeddings = sbert_model.encode(texts, convert_to_numpy=True)
    if embeddings.shape[1] != 768:
        embeddings = embeddings.reshape(-1, 768)

    # Reset FAISS index
    index = faiss.IndexFlatL2(768)
    documents_db = doc_ids
    index.add(embeddings)

    # Build word frequency
    word_frequency = Counter(word_list)

def suggest_documents(query, top_n=5):
    """Suggests similar documents using FAISS."""
    global index, documents_db
    if index.ntotal == 0:
        index_documents()  # Rebuild if empty

    query_embedding = sbert_model.encode([query], convert_to_numpy=True)
    if query_embedding.shape[1] != 768:
        query_embedding = query_embedding.reshape(-1, 768)

    _, indices = index.search(query_embedding, top_n)
    suggested_docs = []
    for i in indices[0]:
        if i < len(documents_db):
            try:
                doc = Document.objects.get(id=documents_db[i])
                suggested_docs.append(doc)
            except Document.DoesNotExist:
                continue

    # Format results
    results = []
    for doc in suggested_docs:
        original_name = os.path.basename(doc.file.name).split('_')[0]
        results.append({
            "file_path": default_storage.url(doc.file.name),
            "name": unquote(original_name)
        })
    return results

def search_documents(query):
    """A completely rebuilt search function that prioritizes exact matches and file extensions."""
    query_lower = query.lower().strip()
    
    # Split the results into different relevance tiers
    exact_matches = []
    partial_matches = []
    fallback_matches = []
    
    # Check if query contains an extension
    file_extension = None
    search_term = query_lower
    if '.' in query_lower:
        parts = query_lower.rsplit('.', 1)
        search_term = parts[0]
        file_extension = parts[1]
    
    # Process all documents
    for doc in Document.objects.all():
        if not doc.file:
            continue
        
        # Get the complete filename and its parts
        filename = os.path.basename(doc.file.name)
        filename_lower = filename.lower()
        
        # Get base part and extension
        doc_base = filename_lower
        doc_ext = None
        if '.' in filename_lower:
            doc_base, doc_ext = filename_lower.rsplit('.', 1)
        
        # Extension filtering
        if file_extension and (not doc_ext or doc_ext != file_extension):
            continue
            
        # Find a clean name (without random suffixes)
        clean_name = doc_base
        if '_' in clean_name:
            # Django often adds _RANDOM to uploaded files
            clean_name = clean_name.split('_')[0]
        elif ' ' in clean_name:
            # Handle "file (1)" type names
            clean_name = re.sub(r' \(\d+\)$', '', clean_name)
        
        # TIER 1: Exact matches in name
        if search_term == clean_name or search_term in clean_name.split():
            exact_matches.append(doc)
            continue
            
        # TIER 2: Partial matches at word boundaries
        if any(word.startswith(search_term) for word in clean_name.split()):
            partial_matches.append(doc)
            continue
            
        # TIER 3: Character-based partial matches
        if len(search_term) >= 3 and search_term[:3] in clean_name:
            partial_matches.append(doc)
            continue
            
        # TIER 4: Fuzzy matching as last resort
        fuzzy_score = fuzz.partial_ratio(search_term, clean_name)
        if fuzzy_score > 70:
            partial_matches.append(doc)
            continue
        elif fuzzy_score > 50:
            fallback_matches.append(doc)
            continue
            
        # TIER 5: Check extracted text
        if doc.extracted_text and search_term in doc.extracted_text.lower():
            fallback_matches.append(doc)
    
    # Combine results in order of relevance
    combined_results = exact_matches + partial_matches + fallback_matches
    
    # Remove duplicates
    seen = set()
    matched_documents = [doc for doc in combined_results if doc.id not in seen and not seen.add(doc.id)]
    
    # Format results
    results = []
    for doc in matched_documents[:5]:  # Limit to top 5
        display_name = os.path.basename(doc.file.name)
        # Clean up the display name
        if '_' in display_name:
            display_name = display_name.split('_')[0]
        
        results.append({
            "file_path": default_storage.url(doc.file.name),
            "name": unquote(display_name)
        })
    
    return results