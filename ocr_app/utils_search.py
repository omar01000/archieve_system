import re
import os
import faiss
from django.conf import settings
from sentence_transformers import SentenceTransformer
from archievesystem.models import Document
from urllib.parse import unquote, quote
from django.core.files.storage import default_storage
from collections import Counter
from rapidfuzz import process, fuzz
import numpy as np

# Use multilingual model that supports Arabic and English well
sbert_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# Optimized globals
index = None
documents_db = []
word_frequency = Counter()

# Smaller cache for speed
embedding_cache = {}
CACHE_SIZE = 300

def get_original_filename(stored_name):
    """Extract original filename without timestamp or extension"""
    # Remove storage path if present
    filename = os.path.basename(stored_name)
    
    # Remove timestamp prefix (format: timestamp_originalname.ext)
    if '_' in filename:
        # Split only once to preserve underscores in original name
        parts = filename.split('_', 1)
        if len(parts) > 1 and parts[0].isdigit():
            filename = parts[1]
    
    # Remove file extension
    if '.' in filename:
        filename = filename.rsplit('.', 1)[0]
    
    return unquote(filename)

def get_file_url_info(doc):
    """Get comprehensive file URL information with proper encoding"""
    if not doc.file:
        return {
            'file_path': None,
            'url': None,
            'download_url': None,
            'media_url': None,
            'direct_media_url': None
        }
    
    # Get the filename only
    base_name = os.path.basename(doc.file.name)
    encoded_name = quote(base_name)  # Properly encode special characters
    
    # Build the direct URL at the root
    direct_media_url = f"/{encoded_name}"
    
    # The default storage URL
    file_url = default_storage.url(doc.file.name)
    
    return {
        'file_path': file_url,
        'url': file_url,
        'download_url': f"/api/documents/{doc.id}/download/",
        'media_url': file_url,
        'direct_media_url': direct_media_url
    }

def build_document_dict(doc, score=None, name=None, direct_media_url=None):
    """Build comprehensive document dictionary with relationships"""
    # Get URL info if not provided
    if direct_media_url is None:
        url_info = get_file_url_info(doc)
        direct_media_url = url_info['direct_media_url']
    
    # Get original filename if not provided
    if name is None and doc.file:
        name = get_original_filename(doc.file.name)
    
    return {
        "id": doc.id,
        "internal_entity": None if not doc.internal_entity else {
            "id": doc.internal_entity.id,
            "name": doc.internal_entity.name
        },
        "internal_department": None if not doc.internal_department else {
            "id": doc.internal_department.id,
            "name": doc.internal_department.name
        },
        "external_entity": None if not doc.external_entity else {
            "id": doc.external_entity.id,
            "name": doc.external_entity.name
        },
        "external_department": None if not doc.external_department else {
            "id": doc.external_department.id,
            "name": doc.external_department.name,
            "external_entity": doc.external_department.external_entity.id 
                                if doc.external_department.external_entity else None
        },
        "uploaded_by": {
            "id": doc.uploaded_by.id,
            "username": doc.uploaded_by.username
        } if doc.uploaded_by else None,
        "last_modified_by": {
            "id": doc.last_modified_by.id,
            "username": doc.last_modified_by.username
        } if doc.last_modified_by else None,
        "title": doc.title,
        "document_number": doc.document_number,
        "notes": doc.notes,
        "entity_type": doc.entity_type,
        "document_type": doc.document_type,
        "file": get_file_url_info(doc)['url'] if doc.file else None,
        "uploaded_at": doc.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") 
                        if doc.uploaded_at else None,
        "modified_at": doc.modified_at.strftime("%Y-%m-%d %H:%M:%S") 
                       if doc.modified_at else None,
        "score": score,
        "name": name,
        "direct_media_url": direct_media_url
    }

def advanced_normalize_text(text):
    """Arabic text normalization with special character preservation"""
    if not text:
        return ""
    
    # Multiple URL decoding attempts
    for _ in range(3):
        try:
            if '%' in text:
                decoded = unquote(text)
                if decoded != text:
                    text = decoded
                else:
                    break
        except:
            break
    
    # Extended Arabic diacritics removal
    text = re.sub(r'[\u064B-\u0652\u0670\u0640\u06D6-\u06ED\u08F0-\u08FF]', '', text)
    
    # Comprehensive Arabic letter normalizations
    arabic_normalizations = {
        'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',
        'ة': 'ه', 
        'ى': 'ي', 'ئ': 'ý', 'ؤ': 'و',
        'ك': 'ك', 'ی': 'ي', 'ے': 'ي',
        '\u200c': '', '\u200d': '', '\u200e': '', '\u200f': '',
    }
    
    for old_char, new_char in arabic_normalizations.items():
        text = text.replace(old_char, new_char)
    
    # Convert to lowercase
    text = text.lower()
    
    # Preserve underscores and hyphens in Arabic phrases
    text = re.sub(r'[\|/\\]+', ' ', text)
    
    # Remove extra punctuation but preserve Arabic-English-numbers
    text = re.sub(r'[^\w\s\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF_-]', ' ', text)
    
    # Normalize multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def extract_arabic_variants(word):
    """Generate common Arabic spelling variants"""
    if not word or len(word) < 2:
        return [word]
    
    variants = [word]
    
    # Common Arabic letter substitutions
    substitutions = {
        'ا': ['أ', 'إ', 'آ'],
        'ي': ['ى', 'ئ'],
        'ه': ['ة'],
        'ة': ['ه'],
        'و': ['ؤ'],
        'ت': ['ة'],
    }
    
    # Generate variants by substituting letters
    for original, replacements in substitutions.items():
        if original in word:
            for replacement in replacements:
                variants.append(word.replace(original, replacement))
    
    # Generate phrase variants with different separators
    if '_' in word or '-' in word:
        variants.append(word.replace('_', '-'))
        variants.append(word.replace('-', '_'))
        variants.append(word.replace('_', ' '))
        variants.append(word.replace('-', ' '))
    
    # Remove duplicates while preserving order
    seen = set()
    return [v for v in variants if v not in seen and v not in seen and not seen.add(v)][:10]

def enhanced_extract_search_terms(text, max_terms=40):
    """Search term extraction with Arabic phrase support"""
    if not text:
        return []
    
    normalized = advanced_normalize_text(text)
    
    # Extract Arabic words and phrases
    arabic_pattern = r'[\w\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF_-]{2,}'
    arabic_terms = re.findall(arabic_pattern, normalized)
    
    # Extract English words
    english_words = re.findall(r'[a-z]{2,}', normalized)
    
    # Extract numbers
    numbers = re.findall(r'\d+', normalized)
    
    # Process Arabic terms with variants
    all_terms = []
    
    # Add original Arabic terms and variants
    for term in arabic_terms:
        if re.search(r'[\u0600-\u06FF]', term):
            all_terms.append(term)
            variants = extract_arabic_variants(term)
            all_terms.extend(variants[1:5])
    
    # Add English terms
    all_terms.extend([word for word in english_words if len(word) >= 2])
    
    # Add numbers
    all_terms.extend(numbers)
    
    # Remove duplicates
    seen = set()
    return [t.strip() for t in all_terms if t and t not in seen and not seen.add(t)][:max_terms]

def arabic_similarity_score(query_term, filename_term):
    """Similarity scoring with exact match priority"""
    if not query_term or not filename_term:
        return 0
    
    # Exact match gets highest score
    if query_term == filename_term:
        return 100
    
    # Exact match with different separators
    if query_term.replace('_', '-') == filename_term.replace('_', '-'):
        return 95
    if query_term.replace('_', ' ') == filename_term.replace('_', ' '):
        return 90
    
    # Phrase matching
    if '_' in query_term or '-' in query_term:
        # Check for phrase as substring
        if query_term in filename_term:
            return 90
        if filename_term in query_term:
            return 85
        
        # Check phrase variants
        variants = extract_arabic_variants(query_term)
        for variant in variants:
            if variant == filename_term:
                return 88
            if variant in filename_term:
                return 80
    
    # Check if both are Arabic
    query_is_arabic = bool(re.search(r'[\u0600-\u06FF]', query_term))
    filename_is_arabic = bool(re.search(r'[\u0600-\u06FF]', filename_term))
    
    if not (query_is_arabic or filename_is_arabic):
        return fuzz.ratio(query_term, filename_term)
    
    # Generate variants for both terms
    query_variants = extract_arabic_variants(query_term)
    filename_variants = extract_arabic_variants(filename_term)
    
    # Check variants against each other
    max_score = 0
    for q_var in query_variants:
        for f_var in filename_variants:
            score = fuzz.ratio(q_var, f_var)
            max_score = max(max_score, score)
    
    # Substring matching
    if len(query_term) >= 3:
        if query_term in filename_term:
            max_score = max(max_score, 85)
        if filename_term in query_term:
            max_score = max(max_score, 80)
    
    return max_score

def get_fast_index(embeddings):
    """Create optimized FAISS index"""
    n_docs, dim = embeddings.shape
    
    if n_docs < 500:
        return faiss.IndexFlatL2(dim)
    elif n_docs < 2000:
        nlist = max(8, n_docs // 30)
        quantizer = faiss.IndexFlatL2(dim)
        index = faiss.IndexIVFFlat(quantizer, dim, nlist)
        index.train(embeddings)
        return index
    else:
        nlist = max(16, min(128, n_docs // 25))
        m = 8
        quantizer = faiss.IndexFlatL2(dim)
        index = faiss.IndexIVFPQ(quantizer, dim, nlist, m, 8)
        index.train(embeddings)
        return index

def index_documents():
    """Enhanced indexing with original filename preservation"""
    global index, documents_db, word_frequency
    
    documents = Document.objects.all()
    texts = []
    doc_ids = []
    all_terms = []

    for doc in documents:
        doc_content = ""
        filename_terms = []
        
        # Process filename
        if doc.file:
            # Get original filename without timestamp/extension
            original_name = get_original_filename(doc.file.name)
            doc_content = original_name
            
            # Add filename terms with variants
            filename_terms = enhanced_extract_search_terms(
                advanced_normalize_text(original_name), 
                25
            )
            all_terms.extend(filename_terms)
            
            # Boost Arabic terms
            arabic_terms = [t for t in filename_terms if re.search(r'[\u0600-\u06FF]', t)]
            all_terms.extend(arabic_terms * 3)
        
        # Process content
        if doc.extracted_text:
            # Take larger content sample for Arabic
            text_sample = doc.extracted_text[:3000]
            text_normalized = advanced_normalize_text(text_sample)
            doc_content = f"{doc_content} {text_normalized}".strip()
            
            # Add text terms with variants
            text_terms = enhanced_extract_search_terms(text_normalized, 40)
            all_terms.extend(text_terms)
            
            # Boost Arabic content terms
            arabic_terms = [t for t in text_terms if re.search(r'[\u0600-\u06FF]', t)]
            all_terms.extend(arabic_terms * 2)
        
        if doc_content:
            texts.append(doc_content)
            doc_ids.append(doc.id)

    if not texts:
        return

    # Create embeddings
    batch_size = 12
    all_embeddings = []
    
    try:
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = sbert_model.encode(
                batch, 
                convert_to_numpy=True, 
                show_progress_bar=False,
                normalize_embeddings=True
            )
            all_embeddings.append(embeddings)
        
        if all_embeddings:
            embeddings = np.vstack(all_embeddings)
            
            # Create fast index
            index = get_fast_index(embeddings)
            documents_db = doc_ids
            index.add(embeddings)
            
            # Build term frequency
            word_frequency = Counter(all_terms)
            if len(word_frequency) > 3000:
                word_frequency = Counter(dict(word_frequency.most_common(3000)))
                
    except Exception as e:
        print(f"Indexing error: {e}")
        index = None

def suggest_documents(query, top_n=4):
    """Document suggestions with comprehensive document data"""
    global index, documents_db, embedding_cache
    
    if index is None or (hasattr(index, 'ntotal') and index.ntotal == 0):
        index_documents()
        if index is None or index.ntotal == 0:
            return []

    # Preprocess query
    processed_query = advanced_normalize_text(query)
    if len(processed_query) < 2:
        return []

    # Check cache
    if processed_query in embedding_cache:
        query_embedding = embedding_cache[processed_query]
    else:
        try:
            query_embedding = sbert_model.encode(
                [processed_query], 
                convert_to_numpy=True, 
                show_progress_bar=False,
                normalize_embeddings=True
            )
            
            # Manage cache
            if len(embedding_cache) >= CACHE_SIZE:
                embedding_cache = dict(list(embedding_cache.items())[CACHE_SIZE//2:])
            
            embedding_cache[processed_query] = query_embedding
        except:
            return []

    # Perform search
    try:
        if hasattr(index, 'nprobe'):
            index.nprobe = min(6, getattr(index, 'nlist', 6))
        
        search_count = min(top_n * 4, index.ntotal)
        distances, indices = index.search(query_embedding, search_count)
        
        candidate_ids = []
        candidate_dists = []
        for j, i in enumerate(indices[0]):
            if i != -1 and i < len(documents_db):
                candidate_ids.append(documents_db[i])
                candidate_dists.append(distances[0][j])
                if len(candidate_ids) >= top_n:
                    break
        
        if not candidate_ids:
            return []
        
        # Fetch documents with relationships
        documents = Document.objects.filter(id__in=candidate_ids).select_related(
            'internal_entity',
            'internal_department',
            'external_entity',
            'external_department',
            'external_department__external_entity',
            'uploaded_by',
            'last_modified_by'
        )
        
        # Create mapping for quick access
        id_to_doc = {doc.id: doc for doc in documents}
        
        results = []
        for doc_id, dist in zip(candidate_ids, candidate_dists):
            if doc_id not in id_to_doc:
                continue
                
            doc = id_to_doc[doc_id]
            
            # Calculate similarity score (0-100)
            # Convert L2 distance to cosine similarity
            cosine_sim = 1 - (dist ** 2) / 2.0
            score = max(0, int(cosine_sim * 100))
            
            # Get original filename
            original_name = get_original_filename(doc.file.name) if doc.file else None
            
            # Get URL info
            url_info = get_file_url_info(doc)
            
            # Build full document dictionary
            document_dict = build_document_dict(
                doc,
                score=score,
                name=original_name,
                direct_media_url=url_info['direct_media_url']
            )
            
            results.append(document_dict)
        
        return results
    except Exception as e:
        print(f"Suggest documents error: {e}")
        return []

def search_documents(query):
    """High-accuracy search with comprehensive document data"""
    if not query or len(query.strip()) < 2:
        return []
    
    raw_query = query
    processed_query = advanced_normalize_text(query)
    if not processed_query:
        return []
    
    # Extract search terms
    query_terms = enhanced_extract_search_terms(processed_query, 12)
    if not query_terms:
        return []
    
    # Detect Arabic content
    has_arabic = any(re.search(r'[\u0600-\u06FF]', t) for t in query_terms)
    
    # File extension handling
    file_extension = None
    if '.' in query and not has_arabic:
        parts = query.strip().lower().rsplit('.', 1)
        if len(parts) == 2 and len(parts[1]) <= 4:
            file_extension = parts[1]
            query_terms = enhanced_extract_search_terms(parts[0], 8)
    
    # Optimized database query with select_related
    documents = Document.objects.select_related(
        'internal_entity',
        'internal_department',
        'external_entity',
        'external_department',
        'external_department__external_entity',
        'uploaded_by',
        'last_modified_by'
    ).all()[:1500 if has_arabic else 800]
    
    scored_results = []
    seen_ids = set()
    
    for doc in documents:
        if len(scored_results) >= (25 if has_arabic else 15):
            break
            
        if not doc.file or doc.id in seen_ids:
            continue
            
        # Get filename and URL info
        original_name = get_original_filename(doc.file.name)
        stored_filename = os.path.basename(doc.file.name)
        url_info = get_file_url_info(doc)
        
        # Extension filtering
        if file_extension and not stored_filename.lower().endswith(f'.{file_extension}'):
            continue
        
        # Prepare for matching
        filename_normalized = advanced_normalize_text(original_name)
        filename_terms = enhanced_extract_search_terms(filename_normalized, 25)
        
        # Scoring
        score = 0
        
        # 1. Exact match bonus
        if raw_query.lower() == original_name.lower():
            score += 1000
        # 2. Raw query in filename
        elif raw_query.lower() in original_name.lower():
            score += 200
        # 3. Normalized exact match
        elif processed_query == filename_normalized:
            score += 150
        # 4. Phrase matching
        if ('_' in raw_query or '-' in raw_query) and raw_query in original_name:
            score += 100
        
        # 5. Term-based matching
        for query_term in query_terms:
            best_match_score = max(
                (arabic_similarity_score(query_term, filename_term) 
                 for filename_term in filename_terms),
                default=0
            )
            if best_match_score >= 90:
                score += 40
            elif best_match_score >= 80:
                score += 30
            elif best_match_score >= 70:
                score += 20
            elif best_match_score >= 60:
                score += 15
            elif best_match_score >= 50:
                score += 10
        
        # 6. Content matching
        if doc.extracted_text:
            content_sample = doc.extracted_text[:1500]
            normalized_content = advanced_normalize_text(content_sample)
            
            if raw_query in content_sample:
                score += 50
            elif processed_query in normalized_content:
                score += 40
            
            for term in query_terms:
                if term in normalized_content:
                    score += 8 if re.search(r'[\u0600-\u06FF]', term) else 5
        
        # Threshold filtering
        min_score = 20 if has_arabic else 25
        if score >= min_score:
            # Build full document dictionary
            document_dict = build_document_dict(
                doc,
                score=score,
                name=original_name,
                direct_media_url=url_info['direct_media_url']
            )
            
            scored_results.append(document_dict)
            seen_ids.add(doc.id)
    
    # Sort and limit results
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return scored_results[:20 if has_arabic else 12]

def get_word_suggestions(query, limit=8):
    """Arabic-aware word suggestions"""
    if not query or len(query) < 2:
        return []
    
    processed_query = advanced_normalize_text(query)
    if not processed_query:
        return []
    
    suggestions = []
    
    if word_frequency:
        has_arabic = bool(re.search(r'[\u0600-\u06FF]', processed_query))
        candidate_limit = limit * 6
        
        # Get initial matches
        matches = process.extract(
            processed_query, 
            word_frequency.keys(), 
            limit=candidate_limit,
            scorer=fuzz.ratio
        )
        
        # Process matches
        arabic_suggestions = []
        other_suggestions = []
        
        for word, score in matches:
            if score < 30:
                continue
                
            if has_arabic and re.search(r'[\u0600-\u06FF]', word):
                arabic_score = arabic_similarity_score(processed_query, word)
                if arabic_score >= 40:
                    arabic_suggestions.append((word, arabic_score))
            elif not has_arabic:
                other_suggestions.append((word, score))
        
        # Sort suggestions
        arabic_suggestions.sort(key=lambda x: x[1], reverse=True)
        other_suggestions.sort(key=lambda x: x[1], reverse=True)
        
        # Combine results
        suggestions = [w for w, _ in arabic_suggestions[:limit]]
        if len(suggestions) < limit:
            suggestions.extend([w for w, _ in other_suggestions[:limit - len(suggestions)]])
    
    return suggestions[:limit]

# Initialize index on startup
def ensure_index():
    global index
    if index is None or (hasattr(index, 'ntotal') and index.ntotal == 0):
        index_documents()

# Initial indexing
ensure_index()