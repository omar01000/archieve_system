# services/document_services.py
import os
import logging
import tempfile
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from rest_framework.views import APIView
from rest_framework.response import Response
from .utils_ocr import extract_text_from_image, extract_text_from_pdf, extract_text_from_word
from .utils_search import search_documents, suggest_documents, reindex_documents
from archievesystem.models import Document

logger = logging.getLogger(__name__)

def validate_file(file):
    """
    Validate uploaded file for size, type, and content.
    
    Args:
        file: Uploaded file object
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Check file size (max 50MB)
    if file.size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        return False, "File size exceeds maximum limit of 50MB"
        
    # Check file type
    allowed_extensions = {'.pdf', '.docx', '.doc', '.jpg', '.jpeg', '.png', '.tiff', '.bmp'}
    file_ext = os.path.splitext(file.name)[1].lower()
    
    if file_ext not in allowed_extensions:
        return False, f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
        
    # Check if file is empty
    if file.size == 0:
        return False, "File is empty"
        
    return True, None

class UploadDocumentService:
    def __init__(self, file, user):
        self.file = file
        self.user = user
    
    def upload(self, document_number=None):
        extracted_text = ""
        document = None
        tmp_file_path = None

        try:
            # Validate file
            is_valid, error_message = validate_file(self.file)
            if not is_valid:
                raise ValueError(error_message)

            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(self.file.name)[-1]) as tmp_file:
                for chunk in self.file.chunks():
                    tmp_file.write(chunk)
                tmp_file_path = tmp_file.name

            # Create the Document instance
            document = Document(
                user=self.user,
                document_number=document_number
            )

            # Reset file pointer before saving
            self.file.seek(0)
            
            # Save the file to the storage
            file_path = default_storage.save(
                f'documents/{self.file.name}',
                ContentFile(self.file.read())
            )
            document.file = file_path

            # Extract text based on file type
            try:
                if self.file.name.lower().endswith(".pdf"):
                    extracted_text, _ = extract_text_from_pdf(tmp_file_path)
                elif self.file.name.lower().endswith((".docx", ".doc")):
                    extracted_text = extract_text_from_word(tmp_file_path)
                else:
                    extracted_text = extract_text_from_image(tmp_file_path)
            except Exception as e:
                logger.error(f"Error extracting text: {str(e)}")
                raise ValueError(f"Failed to extract text from file: {str(e)}")

            # Save the extracted text
            document.extracted_text = extracted_text
            document.save()

            # Reindex documents after successful upload
            try:
                reindex_documents()
            except Exception as e:
                logger.warning(f"Failed to reindex documents: {str(e)}")

            return document, extracted_text

        except Exception as e:
            logger.error(f"Error in upload process: {str(e)}")
            # Clean up the document if it was created but not saved
            if document and document.pk:
                document.delete()
            raise

        finally:
            # Clean up temporary file
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.remove(tmp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file: {str(e)}")

class SearchDocumentView(APIView):
    def get(self, request):
        query = request.GET.get("query", "")
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
        
        if not query:
            return Response({"error": "Query parameter is required"}, status=400)

        try:
            # Get search results with pagination
            results = search_documents(
                query,
                page=page,
                page_size=page_size
            )
            
            # Get suggestions
            suggestions = suggest_documents(query)

            return Response({
                "query": query,
                "results": results,
                "suggestions": suggestions,
                "page": page,
                "page_size": page_size
            })
            
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return Response({
                "error": "An error occurred during search",
                "details": str(e)
            }, status=500)
