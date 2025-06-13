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
    

    
    def upload(self, document_number=None):
        import tempfile
        import os

        extracted_text = ""

        # 👇 نحفظ الملف مؤقتًا، سواء PDF أو صورة
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(self.file.name)[-1]) as tmp_file:
            for chunk in self.file.chunks():
                tmp_file.write(chunk)
            tmp_file_path = tmp_file.name

        # نستدعي الدالة المناسبة حسب نوع الملف
        try:
            if self.file.name.endswith(".pdf"):
                extracted_text = extract_text_from_pdf(tmp_file_path)
            elif self.file.name.endswith(".docx"):
                extracted_text = extract_text_from_word(tmp_file_path)
            else:
                extracted_text = extract_text_from_image(tmp_file_path)
        finally:
            # 👈 امسح الملف بعد ما تخلص
            os.remove(tmp_file_path)

        return None, extracted_text


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
