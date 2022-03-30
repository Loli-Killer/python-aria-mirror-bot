import time
import signal
import shutil
import pickle
import subprocess
from os import execl, path, remove, getcwd
from sys import executable

import psutil
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

import bot
from bot import dispatcher, updater, botStartTime, LOGGER
from bot.helper.ext_utils import fs_utils
from bot.helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, sendLogFile, editMessage
from bot.modules import authorize, list, cancel_mirror, mirror_status, mirror, clone, watch
from bot.custom_mirrors import fembed, xdcc_mirror, cloudflare_mirror, onedrive_mirror


def change_root(update: Update, context: CallbackContext):
    message_args = update.message.text.split(' ')
    bot.PARENT_ID = message_args[1]
    message = f'Changed root drive ID to {bot.PARENT_ID}'
    sendMessage(message, context.bot, update)


def stats(update: Update, context: CallbackContext):
    currentTime = get_readable_time((time.time() - botStartTime))
    total, used, free = shutil.disk_usage('.')
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    cpuUsage = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent
    stats = f'Bot Uptime: {currentTime}\n' \
            f'Total disk space: {total}\n' \
            f'Used: {used}\n' \
            f'Free: {free}\n' \
            f'CPU: {cpuUsage}%\n' \
            f'RAM: {memory}%'
    sendMessage(stats, context.bot, update)


def start(update: Update, context: CallbackContext):
    start_string = f'''
This is a bot which can mirror all your links to Google drive!
Type /{BotCommands.HelpCommand} to get a list of available commands
'''
    sendMessage(start_string, context.bot, update)


def restart(update: Update, context: CallbackContext):
    restart_message = sendMessage("Restarting, Please wait!", context.bot, update)
    # Save restart message object in order to reply to it after restarting
    try:
        fs_utils.clean_all()
    except:
        pass
    with open('restart.pickle', 'wb') as status:
        pickle.dump({
            "message_id": restart_message.message_id,
            "chat_id": restart_message.chat.id
        }, status)
    subprocess.call(path.join(getcwd(), "update.sh"), stdout=subprocess.PIPE, shell=True)
    execl(executable, executable, "-m", "bot")


def ping(update: Update, context: CallbackContext):
    start_time = int(round(time.time() * 1000))
    reply = sendMessage("Starting Ping", context.bot, update)
    end_time = int(round(time.time() * 1000))
    editMessage(f'{end_time - start_time} ms', reply)


def log(update: Update, context: CallbackContext):
    sendLogFile(context.bot, update)


def bot_help(update: Update, context: CallbackContext):
    help_string = f'''
/{BotCommands.HelpCommand}: To get this message

/{BotCommands.MirrorCommand} [download_url][magnet_link]: Start mirroring the link to google drive

/{BotCommands.UnzipMirrorCommand} [download_url][magnet_link] : starts mirroring and if downloaded file is any archive , extracts it to google drive

/{BotCommands.TarMirrorCommand} [download_url][magnet_link]: start mirroring and upload the archived (.tar) version of the download

/{BotCommands.WatchCommand} [youtube-dl supported link]: Mirror through youtube-dl 

/{BotCommands.TarWatchCommand} [youtube-dl supported link]: Mirror through youtube-dl and tar before uploading

/{BotCommands.CancelMirror} : Reply to the message by which the download was initiated and that download will be cancelled

/{BotCommands.StatusCommand}: Shows a status of all the downloads

/{BotCommands.ListCommand} [search term]: Searches the search term in the Google drive, if found replies with the link

/{BotCommands.StatsCommand}: Show Stats of the machine the bot is hosted on

/{BotCommands.AuthorizeCommand}: Authorize a chat or a user to use the bot (Can only be invoked by owner of the bot)

/{BotCommands.LogCommand}: Get a log file of the bot. Handy for getting crash reports

'''
    sendMessage(help_string, context.bot, update)


def main():
    fs_utils.start_cleanup()
    # Check if the bot is restarting
    if path.exists('restart.pickle'):
        with open('restart.pickle', 'rb') as status:
            restart_message = pickle.load(status)
        editMessage("Restarted Successfully!", None, restart_message)
        remove('restart.pickle')

    start_handler = CommandHandler(
        BotCommands.StartCommand, start,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True
    )
    ping_handler = CommandHandler(
        BotCommands.PingCommand, ping,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True
    )
    restart_handler = CommandHandler(
        BotCommands.RestartCommand, restart,
        filters=CustomFilters.owner_filter,
        run_async=True
    )
    help_handler = CommandHandler(
        BotCommands.HelpCommand, bot_help,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True
    )
    stats_handler = CommandHandler(
        BotCommands.StatsCommand, stats,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True
    )
    log_handler = CommandHandler(
        BotCommands.LogCommand, log,
        filters=CustomFilters.owner_filter,
        run_async=True
    )
    change_handler = CommandHandler(
        BotCommands.ChangeRootCommand, change_root,
        filters=CustomFilters.owner_filter,
        run_async=True
    )

    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(ping_handler)
    dispatcher.add_handler(restart_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(stats_handler)
    dispatcher.add_handler(log_handler)
    dispatcher.add_handler(change_handler)

    updater.start_polling()
    LOGGER.info("Bot Started!")
    signal.signal(signal.SIGINT, fs_utils.exit_clean_up)


main()
