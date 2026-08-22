from django.contrib import admin
from .models import Conversation, Message

class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['sender', 'created_at', 'is_read']

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    inlines = [MessageInline]
    list_display = ['subject', 'client', 'message_count', 'unread_count', 'updated_at']
    list_filter = ['client']
    search_fields = ['subject', 'client__username']
    ordering = ['-updated_at']

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for deleted_object in formset.deleted_objects:
            deleted_object.delete()
        for instance in instances:
            if isinstance(instance, Message) and instance.pk is None:
                instance.sender = request.user
            instance.save()
        formset.save_m2m()

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'

    def unread_count(self, obj):
        count = obj.messages.filter(is_read=False).count()
        return f'🔴 {count}' if count > 0 else '✅ 0'
    unread_count.short_description = 'Unread'

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'sender', 'short_body', 'is_read', 'created_at']
    list_filter = ['is_read', 'sender']
    search_fields = ['body', 'sender__username']
    ordering = ['-created_at']
    list_editable = ['is_read']

    def short_body(self, obj):
        return obj.body[:60] + '...' if len(obj.body) > 60 else obj.body
    short_body.short_description = 'Message'
