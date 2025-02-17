from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from bot import dispatcher
from bot.helper.ext_utils.bot_utils import new_thread
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, deleteMessage


@new_thread
def cloneNode(update: Update, context: CallbackContext):
    args = update.message.text.split(" ", maxsplit=1)
    if len(args) > 1:
        link = args[1]
        msg = sendMessage(f"Cloning: <code>{link}</code>", context.bot, update)
        gd = GoogleDriveHelper()
        result = gd.clone(link)
        deleteMessage(context.bot, msg)
        sendMessage(result, context.bot, update)
    else:
        sendMessage("Provide G-Drive Shareable Link to Clone.", context.bot,update)

clone_handler = CommandHandler(
    BotCommands.CloneCommand, cloneNode,
    CustomFilters.authorized_chat | CustomFilters.authorized_user
)
dispatcher.add_handler(clone_handler)