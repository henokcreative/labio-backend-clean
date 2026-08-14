from django.urls import path
from rest_framework.decorators import api_view
from rest_framework.response import Response
from . import views

@api_view(['GET'])
def messaging_root(request):
    """List all available messaging endpoints"""
    return Response({
        'message': 'Messaging API',
        'endpoints': {
            'conversations': '/api/messaging/conversations/ (GET)',
            'conversations_start': '/api/messaging/conversations/start/ (POST)',
            'send_message': '/api/messaging/conversations/<id>/send/ (POST)',
            'mark_read': '/api/messaging/conversations/<id>/mark-read/ (POST)',
            'assign_staff': '/api/messaging/conversations/<id>/assign/ (POST)',
            'unread_count': '/api/messaging/unread/ (GET)',
            'clients': '/api/messaging/clients/ (GET)',
        }
    })

urlpatterns = [
    path('', messaging_root, name='messaging_root'),
    path('conversations/start/', views.start_conversation, name='start_conversation'),
    path('conversations/<int:conversation_id>/send/', views.send_message, name='send_message'),
    path('conversations/<int:conversation_id>/mark-read/', views.mark_read, name='mark_read'),
    path('conversations/<int:conversation_id>/assign/', views.assign_staff, name='assign_staff'),
    path('conversations/', views.get_conversations, name='get_conversations'),
    path('unread/', views.unread_count, name='unread_count'),
    path('clients/', views.get_clients, name='get_clients'),
]