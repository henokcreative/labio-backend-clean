from django.urls import path
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import views


@api_view(['GET'])
def contacts_root(request):
    """List all available contact endpoints"""
    return Response({
        'message': 'Contacts API',
        'endpoints': {
            'messages': '/api/contacts/messages/ (GET, Portal Staff only)',
            'submit': '/api/contacts/submit/ (POST)',
        }
    })

urlpatterns = [
    path('', contacts_root, name='contacts_root'),
    path('messages/', views.get_messages, name='get_messages'),
    path('submit/', views.submit_contact, name='submit_contact'),
]
