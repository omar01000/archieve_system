# services/document_services.py
import os
from django.conf import settings
from django.core.files.storage import default_storage
from .utils_ocr import extract_text_from_image, extract_text_from_pdf, extract_text_from_word
from .utils_search import search_documents, suggest_documents
from archievesystem.models import Document
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status

class UploadDocumentService:
    def __init__(self, file, user):
        self.file = file
        self.user = user

    def upload(self):
        f = self.file
        
        # Save the file to storage first
        file_name = default_storage.save(f.name, f)
        
        # Get the absolute path for OCR processing
        file_path = default_storage.path(file_name)
        
        # Perform OCR based on file type
        if f.name.lower().endswith('.pdf'):
            extracted_text = extract_text_from_pdf(file_path)
        elif f.name.lower().endswith(('.doc', '.docx')):
            extracted_text = extract_text_from_word(file_path)
        else:  # For images
            extracted_text = extract_text_from_image(file_path)

        return file_name, extracted_text


class DocumentUploadView(APIView):
    parser_classes = [MultiPartParser]
    
    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        if 'file' not in request.FILES:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        service = UploadDocumentService(uploaded_file, request.user)
        
        try:
            file_name, extracted_text = service.upload()
        except Exception as e:
            return Response({"error": f"OCR processing failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Create document record
        document = Document(
            user=request.user,
            file=file_name,
            content=extracted_text,
            title=uploaded_file.name
        )
        document.save()
        
        # Build absolute URL for the uploaded file
        file_url = request.build_absolute_uri(default_storage.url(file_name))
        
        return Response({
            "message": "File uploaded successfully",
            "file_url": file_url,
            "document_id": document.id
        }, status=status.HTTP_201_CREATED)


class SearchDocumentView(APIView):
    def get(self, request):
        query = request.GET.get("query", "")
        if not query:
            return Response({"error": "Query parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        results = search_documents(query)
        suggestions = suggest_documents(query)

        # Convert relative URLs to absolute URLs
        base_url = request.build_absolute_uri('/')[:-1]  # Get base URL without trailing slash
        
        def make_absolute(url):
            if url and not url.startswith(('http://', 'https://')):
                # Ensure consistent /media/ prefix
                if not url.startswith('/media/'):
                    url = f"/media/{url.lstrip('/')}"
                return f"{base_url}{url}"
            return url

        # Process results
        for result in results:
            if 'direct_media_url' in result:
                result['direct_media_url'] = make_absolute(result['direct_media_url'])
        
        # Process suggestions
        for suggestion in suggestions:
            if 'direct_media_url' in suggestion:
                suggestion['direct_media_url'] = make_absolute(suggestion['direct_media_url'])

        return Response({
            "query": query,
            "results": results,
            "suggestions": suggestions
        })