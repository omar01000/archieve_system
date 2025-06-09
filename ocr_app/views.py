# services/document_services.py
import os
from django.conf import settings
from django.core.files.storage import default_storage
from .utils_ocr import extract_text_from_image, extract_text_from_pdf, extract_text_from_word
<<<<<<< HEAD
from .utils_search import search_documents, suggest_documents
from archievesystem.models import Document
from rest_framework.views import APIView
from rest_framework.response import Response
=======
from .utils_search import search_documents as utils_search_documents, suggest_documents as utils_suggest_documents
from archievesystem.models import Document

>>>>>>> b7df3cba7f09027ca97d7736157df7ea805ba313
class UploadDocumentService:
    def __init__(self, file, user):
        self.file = file
        self.user = user
<<<<<<< HEAD
    
    def upload(self, document_number=None):  # Add document_number parameter
        # Save file
        relative_file_path = default_storage.save(f"documents/{self.file.name}", self.file)
        file_path = os.path.join(settings.MEDIA_ROOT, relative_file_path)
        
=======

    def upload(self):
        # Save file
        relative_file_path = default_storage.save(f"documents/{self.file.name}", self.file)
        file_path = os.path.join(settings.MEDIA_ROOT, relative_file_path)

>>>>>>> b7df3cba7f09027ca97d7736157df7ea805ba313
        # Extract text
        if self.file.name.endswith(".pdf"):
            extracted_text = extract_text_from_pdf(file_path)
        elif self.file.name.endswith(".docx"):
            extracted_text = extract_text_from_word(file_path)
        else:
            extracted_text = extract_text_from_image(file_path)
<<<<<<< HEAD
        
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
            "results": results,
            "suggestions": suggestions  # Add word suggestions
            
        })
=======

        # Save document
        document = Document.objects.create(
            file=relative_file_path,
            extracted_text=extracted_text,
            uploaded_by=self.user,
            last_modified_by=self.user
        )
        return document, extracted_text

class SearchDocumentsService:
    def __init__(self, query):
        self.query = query

    def search(self):
        results = utils_search_documents(self.query)
        suggestions = utils_suggest_documents(self.query)
        return results, suggestions

>>>>>>> b7df3cba7f09027ca97d7736157df7ea805ba313
