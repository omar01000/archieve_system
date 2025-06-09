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
import numpy as np

# Use a smaller, faster model (384 dimensions instead of 768)
sbert_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# Use quantized FAISS index for smaller memory footprint
index = None
documents_db = []  # Store document IDs
word_frequency = Counter()  # For word suggestions

# Cache for frequently accessed embeddings
embedding_cache = {}
CACHE_SIZE = 1000

def get_optimized_index(embeddings):
    """Create optimized FAISS index based on data size."""
    n_docs, dim = embeddings.shape
    
    if n_docs < 1000:
        # For small datasets, use flat index
        idx = faiss.IndexFlatL2(dim)
    elif n_docs < 10000:
        # For medium datasets, use IVF with fewer clusters
        nlist = min(100, n_docs // 10)
        quantizer = faiss.IndexFlatL2(dim)
        idx = faiss.IndexIVFFlat(quantizer, dim, nlist)
        idx.train(embeddings)
    else:
        # For large datasets, use IVF + PQ for compression
        nlist = min(1000, n_docs // 20)
        m = 8  # Number of subquantizers
        bits = 8  # Bits per subquantizer
        quantizer = faiss.IndexFlatL2(dim)
        idx = faiss.IndexIVFPQ(quantizer, dim, nlist, m, bits)
        idx.train(embeddings)
    
    return idx

def index_documents():
    """Indexes all documents using optimized FAISS and smaller SBERT model."""
    global index, documents_db, word_frequency
    documents = Document.objects.all()

    texts = []
    doc_ids = []
    word_list = []

    for doc in documents:
        # Extract text for indexing (truncate very long texts)
        if doc.extracted_text:
            # Limit text length to improve speed
            text = doc.extracted_text[:2000]  # First 2000 chars
            texts.append(text)
            doc_ids.append(doc.id)

        # Extract words from extracted text and filename for suggestions
        if doc.extracted_text:
            words = re.findall(r"\b\w+\b", doc.extracted_text.lower())
            word_list.extend(words[:100])  # Limit words per document
        
        if doc.file:
            # Extract original filename part before the first underscore
            original_name = os.path.basename(doc.file.name).split('_')[0]
            words = re.findall(r"\b\w+\b", original_name.lower())
            word_list.extend(words)

    if not texts:
        return  # No documents to index

    # Encode documents with batch processing for speed
    batch_size = 32
    all_embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = sbert_model.encode(batch, convert_to_numpy=True, show_progress_bar=False)
        all_embeddings.append(embeddings)
    
    embeddings = np.vstack(all_embeddings)
    
    # Use optimized index
    index = get_optimized_index(embeddings)
    documents_db = doc_ids
    index.add(embeddings)

    # Build word frequency (limit size)
    word_frequency = Counter(word_list)
    # Keep only top 5000 most frequent words
    if len(word_frequency) > 5000:
        word_frequency = Counter(dict(word_frequency.most_common(5000)))

def suggest_documents(query, top_n=5):
    """Suggests similar documents using optimized FAISS."""
    global index, documents_db, embedding_cache
    
    if index is None or index.ntotal == 0:
        index_documents()  # Rebuild if empty

    # Check cache first
    cache_key = query.lower().strip()
    if cache_key in embedding_cache:
        query_embedding = embedding_cache[cache_key]
    else:
        query_embedding = sbert_model.encode([query], convert_to_numpy=True, show_progress_bar=False)
        # Cache management
        if len(embedding_cache) >= CACHE_SIZE:
            # Remove oldest entry
            embedding_cache.pop(next(iter(embedding_cache)))
        embedding_cache[cache_key] = query_embedding

    # Search with optimized parameters
    if hasattr(index, 'nprobe'):
        index.nprobe = min(10, index.nlist)  # Limit search scope for speed
    
    _, indices = index.search(query_embedding, min(top_n, index.ntotal))
    
    suggested_docs = []
    for i in indices[0]:
        if i != -1 and i < len(documents_db):
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
    """Optimized search function with early exits and limited processing."""
    query_lower = query.lower().strip()
    
    # Early exit for very short queries
    if len(query_lower) < 2:
        return []
    
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
    
    # Limit document processing for speed
    documents = Document.objects.all()[:1000]  # Process max 1000 docs
    
    # Process documents with early exits
    for doc in documents:
        if not doc.file:
            continue
        
        # Stop if we have enough results
        if len(exact_matches) >= 10:
            break
            
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
            clean_name = clean_name.split('_')[0]
        elif ' ' in clean_name:
            clean_name = re.sub(r' \(\d+\)$', '', clean_name)
        
        # TIER 1: Exact matches in name
        if search_term == clean_name or search_term in clean_name.split():
            exact_matches.append(doc)
            continue
            
        # TIER 2: Partial matches at word boundaries
        if any(word.startswith(search_term) for word in clean_name.split()):
            partial_matches.append(doc)
            continue
            
        # TIER 3: Character-based partial matches (only for longer terms)
        if len(search_term) >= 3 and search_term[:3] in clean_name:
            partial_matches.append(doc)
            continue
            
        # Skip expensive fuzzy matching and text search if we have enough results
        if len(exact_matches) + len(partial_matches) >= 5:
            continue
            
        # TIER 4: Limited fuzzy matching
        if len(search_term) >= 3:
            fuzzy_score = fuzz.partial_ratio(search_term, clean_name)
            if fuzzy_score > 80:  # Higher threshold for speed
                partial_matches.append(doc)
                continue
            elif fuzzy_score > 70:
                fallback_matches.append(doc)
                continue
        
        # TIER 5: Check extracted text (limited)
        if (len(exact_matches) + len(partial_matches) < 3 and 
            doc.extracted_text and len(search_term) >= 3):
            # Only check first 500 chars of extracted text
            text_snippet = doc.extracted_text[:500].lower()
            if search_term in text_snippet:
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

# Optional: Add periodic cleanup function
def cleanup_cache():
    """Clean up cache periodically to free memory."""
    global embedding_cache
    if len(embedding_cache) > CACHE_SIZE // 2:
        # Keep only half of the cache
        items = list(embedding_cache.items())
        embedding_cache = dict(items[len(items)//2:])

# Optional: Lazy loading function
def ensure_index_loaded():
    """Ensure index is loaded only when needed."""
    global index
    if index is None or index.ntotal == 0:
        index_documents()