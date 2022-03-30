from urllib.parse import urlparse

import requests
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from bot import Interval, dispatcher, LOGGER, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL
from bot.modules.mirror import ariaDlManager, MirrorListener
from bot.helper.ext_utils import bot_utils
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage, update_all_messages
from bot.custom_mirrors.custom_mirror_commands import CustomBotCommands


def mirrorcf(update: Update, context: CallbackContext):

    bot = context.bot
    message_args = update.message.text.split(' ')
    try:
        link = message_args[1]
    except IndexError:
        link = ''

    LOGGER.info(link)
    link = link.strip()
    tag = None
    if not bot_utils.is_url(link) and not bot_utils.is_magnet(link):
        sendMessage('No download source provided', bot, update)
        return

    parsed_link = urlparse(link)
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "cmd": "request.get",
        "url": f"{parsed_link.scheme}://{parsed_link.netloc}",
        "maxTimeout": 60000
    }
    r = requests.post('http://localhost:8191/v1', headers=headers, json=data)
    solution = r.json()['solution']
    cf_clearance = solution['cookies'][0]
    cookie_string = f"{cf_clearance['name']}={cf_clearance['value']};"

    aria_options = {
        "header": f"Cookie:{cookie_string}",
        "user-agent": solution['userAgent']
    }

    listener = MirrorListener(bot, update, False, tag)
    ariaDlManager.add_download(f'{DOWNLOAD_DIR}/{listener.uid}/', [link], listener, aria_options)
    sendStatusMessage(update, bot)
    if len(Interval) == 0:
        Interval.append(bot_utils.setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))


cf_handler = CommandHandler(
    CustomBotCommands.CloudflareCommand, mirrorcf,
    CustomFilters.authorized_chat | CustomFilters.authorized_user,
    run_async=True
)
dispatcher.add_handler(cf_handler)
