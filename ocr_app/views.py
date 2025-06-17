# services/document_services.py
import os
from django.conf import settings
from django.core.files.storage import default_storage
from .utils_ocr import extract_text_from_image, extract_text_from_pdf, extract_text_from_word
from .utils_search import search_documents, suggest_documents
from archievesystem.models import Document
from rest_framework.views import APIView
from rest_framework.response import Response



# services/document_services.py

from django.core.files.storage import default_storage
from .utils_ocr import extract_text_from_image, extract_text_from_pdf, extract_text_from_word

from django.core.files.storage import default_storage
from .utils_ocr import extract_text_from_pdf, extract_text_from_word, extract_text_from_image

class UploadDocumentService:
    def __init__(self, file, user):
        self.file = file
        self.user = user

    def upload(self):
        saved_path = default_storage.save(f"documents/{self.file.name}", self.file)

        # افتح الملف من Cloudinary
        cloud_file = default_storage.open(saved_path, 'rb')

        # استخدم الملف المفتوح في استخراج النص
        if saved_path.lower().endswith('.pdf'):
            extracted_text = extract_text_from_pdf(cloud_file)
        elif saved_path.lower().endswith('.docx'):
            extracted_text = extract_text_from_word(cloud_file)
        else:
            extracted_text = extract_text_from_image(cloud_file)

        # ❗رجّع الملف كـ File وليس فقط المسار
        return cloud_file, extracted_text

    


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
