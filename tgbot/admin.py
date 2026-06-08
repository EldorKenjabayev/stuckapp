from django.contrib import admin


from .models import TelegramUser, TelegramBotToken, Specialization, Client, Specialist


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'first_name', 'last_name', 'username', 'created_at')
    search_fields = ('telegram_id', 'first_name', 'last_name', 'username')
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')


@admin.register(TelegramBotToken)
class TelegramBotTokenAdmin(admin.ModelAdmin):
    list_display = ('token',)
    search_fields = ('token',)


@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('telegram_user', 'phone_number', 'created_at')
    search_fields = ('telegram_user__first_name', 'telegram_user__last_name', 'phone_number')
   #search_fields = ('telegram_user__first_name', 'telegram_user__last_name', 'specialization__name', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')


@admin.register(Specialist)
class SpecialistAdmin(admin.ModelAdmin):
    list_display = ('telegram_user', 'specialization', 'price', 'rating', 'is_active', 'created_at')
    search_fields = ('telegram_user__first_name', 'telegram_user__last_name', 'specialization__name', 'price', 'rating')
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at', 'is_active')


# @admin.register(ClientSpecialistRelation)
# class ClientSpecialistRelationAdmin(admin.ModelAdmin):
#     list_display = ('client', 'specialist')
#     search_fields = ('client__telegram_user__first_name', 'client__telegram_user__last_name',
#                      'specialist__telegram_user__first_name', 'specialist__telegram_user__last_name')
#     list_filter = ('client', 'specialist')

