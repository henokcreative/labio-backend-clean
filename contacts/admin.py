from django.contrib import admin, messages
from .models import ContactMessage
from clients.models import Client


@admin.action(description="Create client from selected contact")
def create_client_from_contact(modeladmin, request, queryset):
    created = 0
    skipped = 0

    for contact in queryset:
        if Client.objects.filter(email=contact.email).exists():
            skipped += 1
            continue

        Client.objects.create(
            name=contact.name,
            email=contact.email,
        )

        created += 1

    if created:
        modeladmin.message_user(
            request,
            f"{created} client(s) created successfully.",
            messages.SUCCESS,
        )

    if skipped:
        modeladmin.message_user(
            request,
            f"{skipped} contact(s) skipped because a client with that email already exists.",
            messages.WARNING,
        )


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'email',
        'short_message',
        'is_read',
        'submitted_at',
    ]

    list_filter = [
        'is_read',
        'submitted_at',
    ]

    search_fields = [
        'name',
        'email',
        'message',
    ]

    ordering = ['-submitted_at']

    list_editable = ['is_read']

    readonly_fields = [
        'name',
        'email',
        'message',
        'submitted_at',
    ]

    actions = [create_client_from_contact]

    def short_message(self, obj):
        return (
            obj.message[:60] + '...'
            if len(obj.message) > 60
            else obj.message
        )

    short_message.short_description = 'Message'