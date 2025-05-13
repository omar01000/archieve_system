from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username',]  # عشان لما تنشئ سوبر يوزر

    def __str__(self):
        return self.username





# الجهات الداخلية
class InternalEntity(models.Model):
    name = models.CharField(max_length=1000)

    def __str__(self):
        return self.name


class InternalDepartment(models.Model):
    name = models.CharField(max_length=1000)
    internal_entity = models.ForeignKey(InternalEntity, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


# الجهات الخارجية
class ExternalEntity(models.Model):
    name = models.CharField(max_length=1000)

    def __str__(self):
        return self.name


class ExternalDepartment(models.Model):
    name = models.CharField(max_length=1000)
    external_entity = models.ForeignKey(ExternalEntity, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


# الملفات المرفوعة
class Document(models.Model):
    INTERNAL = 'جهة داخلية'
    EXTERNAL = 'جهة خارجية'
    ENTITY_TYPE_CHOICES = [
        (INTERNAL, 'جهة داخلية'),
        (EXTERNAL, 'جهة خارجية'),
    ]

    title = models.CharField(max_length=100)
    document_number = models.CharField(max_length=100, unique=True)
    notes = models.TextField(null=True, blank=True)
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPE_CHOICES)
    internal_entity = models.ForeignKey(InternalEntity, on_delete=models.SET_NULL, null=True, blank=True)
    internal_department = models.ForeignKey(InternalDepartment, on_delete=models.SET_NULL, null=True, blank=True)
    external_entity = models.ForeignKey(ExternalEntity, on_delete=models.SET_NULL, null=True, blank=True)
    external_department = models.ForeignKey(ExternalDepartment, on_delete=models.SET_NULL, null=True, blank=True)
    document_type = models.CharField(max_length=100, choices=[
        ('وارد', 'وارد'),
        ('صادر', 'صادر')
    ],
    verbose_name=" النوع"
)
    file = models.FileField(upload_to='documents/')
    extracted_text = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        
        related_name='uploaded_documents',
        verbose_name="المستخدم الذي رفع الملف"
    )
    
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_documents',
        verbose_name="آخر من عدّل الملف"
    )
    modified_at = models.DateTimeField(auto_now=True)

    

    def __str__(self):
        return f"{self.document_number} - {self.title}"

    def clean(self):
        if self.entity_type == self.INTERNAL:
            if not self.internal_entity or not self.internal_department:
                raise ValidationError("يجب تحديد الجهة والإدارة الداخلية")
            if self.external_entity or self.external_department:
                raise ValidationError("لا يجب تحديد جهة أو إدارة خارجية مع كيان داخلي")
        elif self.entity_type == self.EXTERNAL:
            if not self.external_entity or not self.external_department:
                raise ValidationError("يجب تحديد الجهة والإدارة الخارجية")
            if self.internal_entity or self.internal_department:
                raise ValidationError("لا يجب تحديد جهة أو إدارة داخلية مع كيان خارجي")



        # مثال على التحقق من حجم الملف (اختياري)
        if self.file and self.file.size > 10 * 1024 * 1024:  # 10MB
            raise ValidationError("حجم الملف كبير جدًا")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
