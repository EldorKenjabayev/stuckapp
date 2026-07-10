from django import forms
from django.contrib import admin
from django.contrib.auth.models import User
from .models import (
    WebUser, ChatSession, ChatMessage, SupportGroup, UserRequest, BlockedIP
)





@admin.register(WebUser)
class WebUserAdmin(admin.ModelAdmin):
    list_display = ('name', 'ip_address', 'is_active', 'created_at')
    search_fields = ('name', 'ip_address')
    list_filter = ('is_active', 'created_at')
    readonly_fields = ('session_token', 'created_at', 'ip_address')


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    readonly_fields = ('sender_type', 'message_type', 'content', 'file', 'is_read', 'created_at')
    extra = 0
    can_delete = False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('client', 'specialist', 'started_at', 'is_active', 'ended_at')
    exclude = ('expires_at',)
    list_filter = ('is_active', 'started_at')
    search_fields = ('client__name', 'specialist__name')
    readonly_fields = ('started_at',)
    inlines = [ChatMessageInline]
    actions = ['end_sessions']

    @admin.action(description='Завершить выбранные сессии')
    def end_sessions(self, request, queryset):
        for session in queryset.filter(is_active=True):
            session.end_session()
        self.message_user(request, f'Завершено {queryset.count()} сессий.')


@admin.register(SupportGroup)
class SupportGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'url')
    search_fields = ('name',)
    exclude = ('order',)


@admin.register(UserRequest)
class UserRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'problem_short', 'is_processed', 'created_at')
    list_filter = ('is_processed', 'created_at')
    search_fields = ('name', 'problem')
    list_editable = ('is_processed',)
    readonly_fields = ('created_at',)

    @admin.display(description='Проблема')
    def problem_short(self, obj):
        return obj.problem[:80] + '...' if len(obj.problem) > 80 else obj.problem


@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'reason', 'is_active', 'created_at')
    search_fields = ('ip_address',)
    list_filter = ('is_active',)
    list_editable = ('is_active',)
