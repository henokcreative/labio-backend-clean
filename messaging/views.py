from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import F, Prefetch
from clients.permissions import (
    IsPortalStaff,
    IsPortalStaffOrClient,
    has_portal_staff_access,
)
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPortalStaffOrClient])
def get_conversations(request):
    conversations = Conversation.objects.select_related(
        'client',
        'client__client_profile',
        'assigned_staff',
        'project',
    ).prefetch_related(
        Prefetch(
            'messages',
            queryset=Message.objects.select_related(
                'sender',
                'sender__client_profile',
                'conversation',
            ).order_by('created_at'),
        )
    )
    if has_portal_staff_access(request.user):
        filter_value = request.query_params.get('filter', 'all')
        if filter_value == 'unread':
            conversations = conversations.filter(
                messages__is_read=False,
                messages__sender_id=F('client_id'),
            ).distinct()
        elif filter_value == 'mine':
            conversations = conversations.filter(assigned_staff=request.user)
        elif filter_value == 'unassigned':
            conversations = conversations.filter(assigned_staff__isnull=True)
    else:
        conversations = conversations.filter(client=request.user)
    serializer = ConversationSerializer(
        conversations.order_by('-updated_at'),
        many=True,
        context={'request': request},
    )
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPortalStaffOrClient])
def send_message(request, conversation_id):
    try:
        if has_portal_staff_access(request.user):
            conversation = Conversation.objects.get(id=conversation_id)
        else:
            conversation = Conversation.objects.get(id=conversation_id, client=request.user)
    except Conversation.DoesNotExist:
        return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)

    body = str(request.data.get('body', '')).strip()
    if not body:
        return Response({'body': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)
    if len(body) > 10000:
        return Response(
            {'body': ['Ensure this field has no more than 10000 characters.']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if has_portal_staff_access(request.user):
        incoming = conversation.messages.filter(
            sender=conversation.client,
            is_read=False,
        )
    else:
        incoming = conversation.messages.filter(is_read=False).exclude(
            sender=request.user
        )
    incoming.update(is_read=True)

    message = Message.objects.create(
        conversation=conversation,
        sender=request.user,
        body=body,
    )
    conversation.save(update_fields=['updated_at'])

    serializer = MessageSerializer(message, context={'request': request})
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPortalStaffOrClient])
def mark_read(request, conversation_id):
    try:
        if has_portal_staff_access(request.user):
            conversation = Conversation.objects.get(id=conversation_id)
            unread = conversation.messages.filter(sender=conversation.client, is_read=False)
        else:
            conversation = Conversation.objects.get(id=conversation_id, client=request.user)
            unread = conversation.messages.filter(is_read=False).exclude(sender=request.user)
    except Conversation.DoesNotExist:
        return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
    unread.update(is_read=True)
    return Response({'status': 'marked read'})

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPortalStaff])
def assign_staff(request, conversation_id):
    try:
        conversation = Conversation.objects.get(id=conversation_id)
        conversation.assigned_staff = request.user
        conversation.save()
        return Response({'status': 'assigned', 'staff': request.user.username})
    except Conversation.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPortalStaff])
def start_conversation(request):
    client_id = request.data.get('client_id')
    subject = str(request.data.get('subject', '')).strip()
    if not client_id or not subject:
        return Response(
            {'error': 'client_id and subject are required'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(subject) > 200:
        return Response(
            {'subject': ['Ensure this field has no more than 200 characters.']},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        client = User.objects.get(id=client_id, client_profile__isnull=False, is_active=True)
    except User.DoesNotExist:
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
    conversation = Conversation.objects.create(
        client=client,
        subject=subject,
        assigned_staff=request.user
    )
    serializer = ConversationSerializer(conversation, context={'request': request})
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPortalStaffOrClient])
def unread_count(request):
    if has_portal_staff_access(request.user):
        count = Message.objects.filter(
            is_read=False,
            sender_id=F('conversation__client_id'),
        ).count()
    else:
        count = Message.objects.filter(
            conversation__client=request.user,
            is_read=False,
        ).exclude(sender=request.user).count()
    return Response({'unread': count})

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPortalStaff])
def get_clients(request):
    clients = User.objects.filter(
        client_profile__isnull=False,
        is_active=True,
    ).select_related('client_profile').order_by('client_profile__name')
    return Response([
        {
            'id': client.id,
            'username': client.username,
            'first_name': client.first_name,
            'last_name': client.last_name,
            'name': client.client_profile.name,
        }
        for client in clients
    ])
