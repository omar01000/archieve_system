# services/document_services.py
import os
from django.conf import settings
from django.core.files.storage import default_storage
from .utils_ocr import extract_text_from_image, extract_text_from_pdf, extract_text_from_word
from .utils_search import search_documents, suggest_documents
from archievesystem.models import Document
from rest_framework.views import APIView
from rest_framework.response import Response
class UploadDocumentService:
    def __init__(self, file, user):
        self.file = file
        self.user = user
    
    def upload(self):
        # Clean filename to avoid URL encoding issues
        clean_filename = self.file.name.replace(' ', '_').replace('%', '_')
        
        # Save file and get relative path only
        relative_file_path = default_storage.save(f"documents/{clean_filename}", self.file)
        
        # Build full path for text extraction
        file_path = os.path.join(settings.MEDIA_ROOT, relative_file_path)
        
        # Extract text
        if self.file.name.lower().endswith(".pdf"):
            extracted_text = extract_text_from_pdf(file_path)
        elif self.file.name.lower().endswith(".docx"):
            extracted_text = extract_text_from_word(file_path)
        else:
            extracted_text = extract_text_from_image(file_path)
        
        # Return relative path for database storage
        return relative_file_path, extracted_text

class SearchDocumentView(APIView):
    def get(self, request):
        query = request.GET.get("query", "")
        if not query:
            return Response({"error": "Query parameter is required"}, status=400)

        results = search_documents(query)
        suggestions = suggest_documents(query)

        # Convert relative URLs to absolute URLs
        base_url = request.build_absolute_uri('/')[:-1]  # Get base URL without trailing slash
        
        def make_absolute(url):
            if url and not url.startswith(('http://', 'https://')):
                # Format: http://127.0.0.1:8000/media/documents/Filename.pdf
                return f"{base_url}{url}"
            return url

        for result in results:
            if 'direct_media_url' in result:
                result['direct_media_url'] = make_absolute(result['direct_media_url'])
        
        for suggestion in suggestions:
            if 'direct_media_url' in suggestion:
                suggestion['direct_media_url'] = make_absolute(suggestion['direct_media_url'])

        return Response({
            "query": query,
            "results": results,
            "suggestions": suggestions
        })