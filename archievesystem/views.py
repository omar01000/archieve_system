from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

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


class InternalEntityViewSet(viewsets.ModelViewSet):
    queryset = InternalEntity.objects.all()
    serializer_class = InternalEntitySerializer
    permission_classes = [IsAdminOrReadOnly]

    

class InternalDepartmentViewSet(viewsets.ModelViewSet):
    queryset = InternalDepartment.objects.all()
    serializer_class = InternalDepartmentSerializer
    permission_classes = [IsAdminOrReadOnly]


class ExternalEntityViewSet(viewsets.ModelViewSet):
    queryset = ExternalEntity.objects.all()
    serializer_class = ExternalEntitySerializer
    permission_classes = [IsAdminOrReadOnly]


class ExternalDepartmentViewSet(viewsets.ModelViewSet):
    queryset = ExternalDepartment.objects.all()
    serializer_class = ExternalDepartmentSerializer
    permission_classes = [IsAdminOrReadOnly]





from rest_framework import viewsets
from rest_framework.parsers import MultiPartParser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from .models import Document, InternalEntity, ExternalEntity, InternalDepartment, ExternalDepartment
from .serializers import DocumentSerializer, GetDocumentSerializer, InternalEntitySerializer, ExternalEntitySerializer, InternalDepartmentSerializer, ExternalDepartmentSerializer
from .permissions import IsDocumentAccessible
from django.contrib.auth import get_user_model
from rest_framework import serializers
from ocr_app.views import UploadDocumentService, SearchDocumentsService
User = get_user_model()

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
        'internal_department', 'external_department'
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
        query = self.request.query_params.get('search', None)

        if query:
            search_service = SearchDocumentsService(query)
            results, _ = search_service.search()
            queryset = queryset.filter(id__in=[doc['id'] for doc in results])

        return queryset
    
    def perform_create(self, serializer):
        uploaded_file = self.request.FILES.get('file', None)

        if not uploaded_file:
            raise ValidationError({"error": "No file uploaded."})

        upload_service = UploadDocumentService(file=uploaded_file, user=self.request.user)
        document, extracted_text = upload_service.upload()

        serializer.save(
            uploaded_by=self.request.user,
            last_modified_by=self.request.user,
            file=document.file,
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
