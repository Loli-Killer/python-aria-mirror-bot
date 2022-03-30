import threading

from telegram import Bot, Update
from telegram.ext import CommandHandler, CallbackContext

from bot import Interval, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL, dispatcher
from bot.modules.mirror import MirrorListener
from bot.helper.ext_utils.bot_utils import setInterval
from bot.helper.mirror_utils.download_utils.youtube_dl_download_helper import YoutubeDLHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import update_all_messages, sendMessage, sendStatusMessage


def _watch(bot: Bot, update: Update, args: list, isTar: bool = False):
    try:
        link = args[0]
    except IndexError:
        msg = f"/{BotCommands.WatchCommand} [yt_dl supported link] [quality] to mirror with youtube_dl.\n\n"
        msg += "Example of quality :- audio, 144, 360, 720, 1080.\nNote :- Quality is optional"
        sendMessage(msg, bot, update)
        return
    try:
        qual = args[1]
        if qual != "audio":
            qual = f'best[height<={qual}]/bestvideo[height<={qual}]+bestaudio'
    except IndexError:
        qual = "best/bestvideo+bestaudio"
    reply_to = update.message.reply_to_message
    if reply_to is not None:
        tag = reply_to.from_user.username
    else:
        tag = None

    listener = MirrorListener(bot, update, isTar, tag)
    ydl = YoutubeDLHelper(listener)
    threading.Thread(target=ydl.add_download, args=(link, f'{DOWNLOAD_DIR}{listener.uid}', qual)).start()
    sendStatusMessage(update, bot)
    if len(Interval) == 0:
        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))


def watchTar(update: Update, context: CallbackContext):
    _watch(context.bot, update, context.args, True)


def watch(update: Update, context: CallbackContext):
    _watch(context.bot, update, context.args)


watch_handler = CommandHandler(
    BotCommands.WatchCommand, watch,
    CustomFilters.authorized_chat | CustomFilters.authorized_user,
    run_async=True
)
tar_watch_handler = CommandHandler(
    BotCommands.TarWatchCommand, watchTar,
    CustomFilters.authorized_chat | CustomFilters.authorized_user,
    run_async=True
)
dispatcher.add_handler(watch_handler)
dispatcher.add_handler(tar_watch_handler)
