"""
URL configuration for the advisor app.
"""
from django.urls import path
from . import views

app_name = 'advisor'

urlpatterns = [
    # Home / Dashboard
    path('', views.home, name='home'),
    
    # Connection management
    path('connections/', views.connection_list, name='connection_list'),
    path('connections/add/', views.connection_add, name='connection_add'),
    path('connections/<int:pk>/edit/', views.connection_edit, name='connection_edit'),
    path('connections/<int:pk>/delete/', views.connection_delete, name='connection_delete'),
    path('connections/<int:pk>/test/', views.connection_test, name='connection_test'),
    
    # Query analysis
    path('analyze/<int:connection_id>/', views.analyze_query, name='analyze_query'),
    path('results/<int:query_id>/', views.view_results, name='view_results'),
    
    # History
    path('history/', views.query_history, name='query_history'),
    path('history/<int:pk>/delete/', views.history_delete, name='history_delete'),
    
    # API endpoints for AJAX
    path('api/analyze/', views.api_analyze, name='api_analyze'),
]
