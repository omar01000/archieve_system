from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q




from django.contrib.auth import get_user_model
from rest_framework import serializers
import os
from django.conf import settings
from ocr_app.views import UploadDocumentService
from ocr_app.utils_search import search_documents
from ocr_app.views import UploadDocumentService, SearchDocumentView

from rest_framework.parsers import MultiPartParser
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.exceptions import ValidationError

from .models import Document, InternalEntity, InternalDepartment, ExternalEntity, ExternalDepartment
from .serializers import (
    DocumentSerializer,
    GetDocumentSerializer,
    InternalEntitySerializer,
    ExternalEntitySerializer,
    InternalDepartmentSerializer,
    ExternalDepartmentSerializer
)
from .permissions import IsDocumentAccessible,IsAdminOrReadOnly

User = get_user_model()



class InternalEntityViewSet(viewsets.ModelViewSet):
    queryset = InternalEntity.objects.all()
    serializer_class = InternalEntitySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['name']
    search_fields = ['name']
    

    

class InternalDepartmentViewSet(viewsets.ModelViewSet):
    queryset = InternalDepartment.objects.all()
    serializer_class = InternalDepartmentSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['name','internal_entity']
    search_fields = ['name','internal_entity']


class ExternalEntityViewSet(viewsets.ModelViewSet):
    queryset = ExternalEntity.objects.all()
    serializer_class = ExternalEntitySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]

    filterset_fields = ['name']
    search_fields = ['name']


class ExternalDepartmentViewSet(viewsets.ModelViewSet):
    queryset = ExternalDepartment.objects.all()
    serializer_class = ExternalDepartmentSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['name','external_entity']
    search_fields = ['name','external_entity']









class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username')


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.select_related(
        'uploaded_by',
        'last_modified_by',
        'internal_entity', 'internal_department',
        'external_entity', 'external_department'
    ).all()
    
    parser_classes = [MultiPartParser]
    permission_classes = [IsDocumentAccessible]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = [
        'entity_type', 'document_type',
        'external_entity', 'internal_entity',
        'internal_department', 'external_department','title', 'document_number'
    ]
    search_fields = ['title', 'document_number']

    def get_serializer_class(self):
        if self.request.method == 'GET':
            class GetDocumentWithUsersSerializer(GetDocumentSerializer):
                uploaded_by = UserSimpleSerializer(read_only=True)
                last_modified_by = UserSimpleSerializer(read_only=True)
            return GetDocumentWithUsersSerializer
        return DocumentSerializer


    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.query_params.get('search')

        if not query:
            return queryset

        # ⬅️ استخدم الذكاء الاصطناعي + البحث التقليدي سوا
        ids = []
        for doc in (search_documents(query) or []):
            doc_id = doc.get('id')
            if doc_id:
                ids.append(doc_id)  # سيبها كده لو UUID

        return queryset.filter(
            Q(id__in=ids) |  # ← نتائج الذكاء الاصطناعي
            Q(title__icontains=query) |
            Q(document_number__icontains=query)  # ← بحث تقليدي
        )


    
    
   
    def perform_create(self, serializer):
        uploaded_file = self.request.FILES.get('file')

        if not uploaded_file:
            raise ValidationError({"error": "No file uploaded."})

        document_number = serializer.validated_data.get('document_number')
        if not document_number or not document_number.strip():
            raise ValidationError({"document_number": "Document number cannot be empty."})

        if Document.objects.filter(document_number=document_number).exists():
            raise ValidationError({"document_number": "A document with this number already exists."})

        # ✅ استخدم الملف كما هو - بدون save يدوي
        upload_service = UploadDocumentService(file=uploaded_file, user=self.request.user)
        file_obj, extracted_text = upload_service.upload()

        # هنا Cloudinary هيتعامل مع الملف
        serializer.save(
            uploaded_by=self.request.user,
            last_modified_by=self.request.user,
            file=file_obj,
            extracted_text=extracted_text
        )


        
    def perform_update(self, serializer):
        user = self.request.user

        if user.groups.filter(name='User').exists():
            raise PermissionDenied("المستخدم العادي لا يمكنه تعديل الملفات.")

        # تأمين: الحفاظ على من رفع الملف أول مرة
        instance = self.get_object()
        serializer.save(
            last_modified_by=user,
            uploaded_by=instance.uploaded_by  # ترجيع القيمة الأصلية
    )

    def perform_destroy(self, instance):
        user = self.request.user
        if user.groups.filter(name='User').exists():
            raise PermissionDenied("المستخدم العادي لا يمكنه حذف الملفات.")
        instance.delete()

    @action(detail=False, methods=['get'])
    def get_initial_data(self, request):
        internal_entities = InternalEntity.objects.all()
        external_entities = ExternalEntity.objects.all()
        internal_entity_data = InternalEntitySerializer(internal_entities, many=True).data
        external_entity_data = ExternalEntitySerializer(external_entities, many=True).data
        return Response({
            'internal_entities': internal_entity_data,
            'external_entities': external_entity_data
        })

    @action(detail=False, methods=['get'])
    def get_internal_departments(self, request):
        internal_entity_id = request.query_params.get('internal_entity_id')
        if internal_entity_id:
            internal_departments = InternalDepartment.objects.filter(internal_entity_id=internal_entity_id)
            internal_department_data = InternalDepartmentSerializer(internal_departments, many=True).data
            return Response({'internal_departments': internal_department_data})
        return Response({'error': 'Internal Entity ID is required'}, status=400)

    @action(detail=False, methods=['get'])
    def get_external_departments(self, request):
        external_entity_id = request.query_params.get('external_entity_id')
        if external_entity_id:
            external_departments = ExternalDepartment.objects.filter(external_entity_id=external_entity_id)
            external_department_data = ExternalDepartmentSerializer(external_departments, many=True).data
            return Response({'external_departments': external_department_data})
        return Response({'error': 'External Entity ID is required'}, status=400)
