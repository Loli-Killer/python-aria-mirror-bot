import threading

from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from bot import LOGGER, dispatcher
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import auto_delete_message, sendMessage

def list_drive(update: Update, context: CallbackContext):
    message = update.message.text
    search = message.split(' ', maxsplit=1)[1]
    LOGGER.info(f"Searching: {search}")
    gdrive = GoogleDriveHelper(None)
    msg = gdrive.drive_list(search)
    if msg:
        reply_message = sendMessage(msg, context.bot, update)
    else:
        reply_message = sendMessage('No result found', context.bot, update)

    threading.Thread(target=auto_delete_message, args=(context.bot, update.message, reply_message)).start()


list_handler = CommandHandler(
    BotCommands.ListCommand, list_drive,
    CustomFilters.authorized_chat | CustomFilters.authorized_user,
    run_async=True
)
dispatcher.add_handler(list_handler)
