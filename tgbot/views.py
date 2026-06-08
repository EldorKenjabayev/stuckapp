from django.views.generic import ListView

from tgbot.models import TelegramUser


class TelegramUserView(ListView):
    queryset = TelegramUser.objects.all()
    template_name = 'tgbot/telegram_list.html'

    def get_queryset(self):
        return TelegramUser.objects.all()

