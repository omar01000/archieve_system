from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Document(models.Model):
    """Model for storing OCR processed documents."""
    
    file = models.FileField(
        upload_to='documents/',
        verbose_name=_('Document File'),
        help_text=_('Upload a PDF or image file')
    )
    extracted_text = models.TextField(
        verbose_name=_('Extracted Text'),
        help_text=_('Text extracted from the document using OCR'),
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_('User'),
        related_name='documents'
    )
    document_number = models.CharField(
        max_length=50,
        verbose_name=_('Document Number'),
        help_text=_('Optional document reference number'),
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )

    class Meta:
        verbose_name = _('Document')
        verbose_name_plural = _('Documents')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"Document {self.document_number or self.id}"

    def save(self, *args, **kwargs):
        # Ensure document_number is unique if provided
        if self.document_number:
            self.document_number = self.document_number.strip()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Delete the file when the document is deleted
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)
