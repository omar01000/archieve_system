from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.filters import SearchFilter
from .models import InternalEntity, InternalDepartment, ExternalEntity, ExternalDepartment, Document
from .serializers import InternalEntitySerializer, InternalDepartmentSerializer, ExternalEntitySerializer, ExternalDepartmentSerializer, DocumentSerializer, EntityTypeSerializer,GetDocumentSerializer
from django_filters.rest_framework import DjangoFilterBackend

class InternalEntityViewSet(viewsets.ModelViewSet):
    queryset = InternalEntity.objects.all()
    serializer_class = InternalEntitySerializer
    

class InternalDepartmentViewSet(viewsets.ModelViewSet):
    queryset = InternalDepartment.objects.all()
    serializer_class = InternalDepartmentSerializer

class ExternalEntityViewSet(viewsets.ModelViewSet):
    queryset = ExternalEntity.objects.all()
    serializer_class = ExternalEntitySerializer

class ExternalDepartmentViewSet(viewsets.ModelViewSet):
    queryset = ExternalDepartment.objects.all()
    serializer_class = ExternalDepartmentSerializer

class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    
    parser_classes = [MultiPartParser]
    filter_backends = [DjangoFilterBackend,SearchFilter]
    filterset_fields = ['entity_type','document_type','external_entity','internal_entity','internal_department','external_department']
    search_fields = ['title','document_number'] 
       
    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return GetDocumentSerializer
        return DocumentSerializer
    

    @action(detail=False, methods=['get'])
    def get_initial_data(self, request):
        # إرجاع جميع الجهات الداخلية والخارجية
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
    
    
    