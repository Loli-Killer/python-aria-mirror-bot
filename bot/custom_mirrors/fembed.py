import re

import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from bot import Interval, LOGGER, dispatcher, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL
from bot.modules.mirror import ariaDlManager, MirrorListener
from bot.helper.ext_utils import bot_utils
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage, update_all_messages
from bot.custom_mirrors.custom_mirror_commands import CustomBotCommands


def fembed(update: Update, context: CallbackContext):

    bot = context.bot
    message_args = update.message.text.split(' ')
    try:
        fembed_link = message_args[1]
    except IndexError:
        fembed_link = ''
    LOGGER.info(fembed_link)
    fembed_link = fembed_link.strip()
    tag = None
    if not bot_utils.is_url(fembed_link):
        sendMessage('No download source provided', bot, update)
        return

    aria_options = {}
    fembed_domain = re.match(r".*\/\/(.*?)\/.*", fembed_link, re.MULTILINE).group(1)
    r = requests.get(fembed_link)
    data = BeautifulSoup(r.text, 'html.parser')
    try:
        name = data.find_all('title')[0].text.split(" - Free download")[0]
        aria_options.update({"out": name})
    except IndexError:
        pass
    fembed_id = fembed_link.split("f/")[1]
    fembed_api_link = f"https://{fembed_domain}/api/source/{fembed_id}"
    fembed_link = requests.post(fembed_api_link).json()['data'][-1]['file']

    listener = MirrorListener(bot, update, False, tag)
    ariaDlManager.add_download(f'{DOWNLOAD_DIR}/{listener.uid}/', [fembed_link], listener, aria_options)
    sendStatusMessage(update, bot)
    if len(Interval) == 0:
        Interval.append(bot_utils.setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))


fembed_handler = CommandHandler(
    CustomBotCommands.FembedCommand, fembed,
    CustomFilters.authorized_chat | CustomFilters.authorized_user,
    run_async=True
)
dispatcher.add_handler(fembed_handler)
