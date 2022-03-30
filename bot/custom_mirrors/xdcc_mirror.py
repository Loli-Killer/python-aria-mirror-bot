import re
import binascii

from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from bot import Interval, dispatcher, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL
from bot.modules.mirror import MirrorListener
from bot.helper.ext_utils.bot_utils import get_download_by_gid, setInterval
from bot.helper.mirror_utils.download_utils.xdcc_download_helper import XDCCDownload
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage, update_all_messages
from bot.custom_mirrors.custom_mirror_commands import CustomBotCommands


def xdcc_download(update: Update, context: CallbackContext):

    bot = context.bot
    message_args = update.message.text.split(' ', 2)
    usage_message = 'Xdcc download format is: `/xdcc [server[:port]],]<channel> /msg <bot> xdcc <send|batch> <1|1-5>`\n\n' \
    'Eg: `/xdcc channelname /msg testbot xdcc batch 5-20\n\n`' \
    'Default server is `irc.rizon.net`'

    try:
        server_channel = message_args[1]
    except IndexError:
        sendMessage(usage_message, bot, update, "md")
        return
    server_channel = server_channel.strip()

    try:
        command = message_args[2]
    except IndexError:
        sendMessage(usage_message, bot, update, "md")
        return

    server_channel = server_channel.split(",")
    args = {
        "server": "irc.rizon.net",
        "port": 6667
    }

    if len(server_channel) == 1:
        args.update({"channel": server_channel[0]})
    elif len(server_channel) == 2:
        if ":" in server_channel[0]:
            server_port = server_channel[0].split(":")
            args.update({"server": server_port[0]})
            args.update({"port": server_port[1]})
        else:
            args.update({"server": server_channel[0]})
        args.update({"channel": server_channel[1]})
    else:
        sendMessage(usage_message, bot, update, "md")
        return

    tag = None

    pattern = r".* (.*?) xdcc (send|batch) (.*)"
    commands = re.match(pattern, command)
    args.update({
        "bot": commands.group(1),
        "action": commands.group(2),
        "packs": commands.group(3)
    })

    gid = format(binascii.crc32((args['bot'] + args['packs']).encode('utf8')), '08x')
    if get_download_by_gid(gid):
        sendMessage('Mirror already in queue.', bot, update)
        return

    root = f"/{args['bot']} {args['packs']}/"
    listener = MirrorListener(bot, update, False, tag, root=root)
    xdcc_dl = XDCCDownload(listener)
    xdcc_dl.add_download(args, f'{DOWNLOAD_DIR}{listener.uid}/{root}')
    sendStatusMessage(update, bot)
    if len(Interval) == 0:
        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))


xdcc_handler = CommandHandler(
    CustomBotCommands.XdccCommand, xdcc_download,
    CustomFilters.authorized_chat | CustomFilters.authorized_user,
    run_async=True
)
dispatcher.add_handler(xdcc_handler)
