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
    
    def upload(self, document_number=None):  # Add document_number parameter
        # Save file
        relative_file_path = default_storage.save(f"documents/{self.file.name}", self.file)
        file_path = os.path.join(settings.MEDIA_ROOT, relative_file_path)
        
        # Extract text
        if self.file.name.endswith(".pdf"):
            extracted_text = extract_text_from_pdf(file_path)
        elif self.file.name.endswith(".docx"):
            extracted_text = extract_text_from_word(file_path)
        else:
            extracted_text = extract_text_from_image(file_path)
        
        # Don't create the document here, just return the file path and extracted text
        return relative_file_path, extracted_text

class SearchDocumentView(APIView):
    def get(self, request):
        query = request.GET.get("query", "")
        if not query:
            return Response({"error": "Query parameter is required"}, status=400)

        results = search_documents(query)  # Search for matching documents
        suggestions = suggest_documents(query)  # Get Google-like autocomplete suggestions

        return Response({
            "query": query,
            "suggestions": suggestions,  # Add word suggestions
            "results": results
        })
