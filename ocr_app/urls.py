from django.urls import path
from .views import  SearchDocumentView

urlpatterns = [
    
    path('search_with_ai/', SearchDocumentView.as_view(), name='search_document'),
]