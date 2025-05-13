from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InternalEntityViewSet, InternalDepartmentViewSet, ExternalEntityViewSet, ExternalDepartmentViewSet, DocumentViewSet

router = DefaultRouter()
router.register(r'internal_entities', InternalEntityViewSet)
router.register(r'internal_departments', InternalDepartmentViewSet)
router.register(r'external_entities', ExternalEntityViewSet)
router.register(r'external_departments', ExternalDepartmentViewSet)
router.register(r'documents', DocumentViewSet)

urlpatterns = [
    path('', include(router.urls)),
]