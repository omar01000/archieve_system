# services/document_services.py
import os
from django.conf import settings
from django.core.files.storage import default_storage
from .utils_ocr import extract_text_from_image, extract_text_from_pdf, extract_text_from_word
from .utils_search import search_documents as utils_search_documents, suggest_documents as utils_suggest_documents
from archievesystem.models import Document

class UploadDocumentService:
    def __init__(self, file, user):
        self.file = file
        self.user = user

    def upload(self):
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

