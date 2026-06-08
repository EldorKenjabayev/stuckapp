import os
import sys
import django

# Set up Django environment
sys.path.append('/home/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Fenix.settings')
django.setup()

import requests
from django.conf import settings
from tgbot.models import Specialist
from tgbot.dispatcher import bot
import asyncio

cache_dir = os.path.join(settings.MEDIA_ROOT, 'specialists_cache')
os.makedirs(cache_dir, exist_ok=True)

specs = list(Specialist.objects.filter(is_active=True).values('id', 'name', 'photo_id'))
print(f'Pre-caching {len(specs)} specialists...')

async def download_all():
    count = 0
    for sp in specs:
        if not sp['photo_id']:
            continue
        local_file_path = os.path.join(cache_dir, f"{sp['photo_id']}.jpg")
        if os.path.exists(local_file_path):
            continue
        try:
            print(f"Caching: {sp['name']}")
            file = await bot.get_file(sp['photo_id'])
            file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
            r = requests.get(file_url)
            if r.status_code == 200:
                with open(local_file_path, 'wb') as f:
                    f.write(r.content)
                print(f"Cached {sp['name']}")
                count += 1
        except Exception as e:
            print(f"Error {sp['name']}: {e}")
    print(f'Done! Successfully cached {count} photos.')
    await bot.session.close()

asyncio.run(download_all())
