import os
import pathlib
import subprocess
import threading

import requests
from telegram import Update, Bot
from telegram.ext import CommandHandler, CallbackContext

from bot import Interval, INDEX_URL, LOGGER, MEGA_KEY
from bot import dispatcher, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL, download_dict, download_dict_lock
from bot.helper.ext_utils import fs_utils
from bot.helper.ext_utils.bot_utils import setInterval, is_url, is_magnet, is_mega_link
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException, NotSupportedExtractionArchive
from bot.helper.mirror_utils.download_utils.aria2_download import AriaDownloadHelper
from bot.helper.mirror_utils.download_utils.mega_download import MegaDownloader
from bot.helper.mirror_utils.download_utils.direct_link_generator import direct_link_generator
from bot.helper.mirror_utils.download_utils.telegram_downloader import TelegramDownloadHelper
from bot.helper.mirror_utils.status_utils import listeners
from bot.helper.mirror_utils.status_utils.extract_status import ExtractStatus
from bot.helper.mirror_utils.status_utils.tar_status import TarStatus
from bot.helper.mirror_utils.status_utils.upload_status import UploadStatus
from bot.helper.mirror_utils.upload_utils import gdriveTools
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import delete_all_messages, sendMessage, \
    sendStatusMessage, update_all_messages

ariaDlManager = AriaDownloadHelper()
ariaDlManager.start_listener()


class MirrorListener(listeners.MirrorListeners):
    def __init__(
        self, bot: Bot, update: Update,
        isTar: bool = False,
        tag:str = None,
        extract: bool = False,
        root: str = ""
    ):
        super().__init__(bot, update)
        self.isTar = isTar
        self.tag = tag
        self.extract = extract
        self.root = root

    def onDownloadStarted(self):
        pass

    def onDownloadProgress(self):
        # We are handling this on our own!
        pass

    def clean(self):
        try:
            Interval[0].cancel()
            del Interval[0]
            delete_all_messages()
        except IndexError:
            pass

    def onDownloadComplete(self):
        with download_dict_lock:
            LOGGER.info(f"Download completed: {download_dict[self.uid].name()}")
            download = download_dict[self.uid]
            name = download.name()
            size = download.size_raw()
            if name is None: # when pyrogram's media.file_name is of NoneType
                name = os.listdir(f'{DOWNLOAD_DIR}{self.uid}')[0]
            m_path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        if self.isTar:
            download.is_archiving = True
            try:
                with download_dict_lock:
                    download_dict[self.uid] = TarStatus(name, m_path, size)
                path = fs_utils.tar(m_path)
            except FileNotFoundError:
                LOGGER.info('File to archive not found!')
                self.onUploadError('Internal error occurred!!')
                return
        elif self.extract:
            download.is_extracting = True
            try:
                path = fs_utils.get_base_name(m_path)
                LOGGER.info(
                    f"Extracting : {name} "
                )
                with download_dict_lock:
                    download_dict[self.uid] = ExtractStatus(name, m_path, size)
                archive_result = subprocess.run(["extract", m_path])
                if archive_result.returncode == 0:
                    threading.Thread(target=os.remove, args=(m_path,)).start()
                    LOGGER.info(f"Deleting archive : {m_path}")
                else:
                    LOGGER.warning('Unable to extract archive! Uploading anyway')
                    path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
                LOGGER.info(
                    f'got path : {path}'
                )

            except NotSupportedExtractionArchive:
                LOGGER.info("Not any valid archive, uploading file as it is.")
                path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        else:
            if self.root:
                path = f'{DOWNLOAD_DIR}{self.uid}/{self.root}'
            else:
                path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        up_name = pathlib.PurePath(path).name
        LOGGER.info(f"Upload Name : {up_name}")
        drive = gdriveTools.GoogleDriveHelper(up_name, self)
        if self.root:
            size = fs_utils.get_path_size(path)
        else:
            if size == 0:
                size = fs_utils.get_path_size(m_path)
        upload_status = UploadStatus(drive, size, self)
        with download_dict_lock:
            download_dict[self.uid] = upload_status
        update_all_messages()
        drive.upload(up_name)

    def onDownloadError(self, error: str):
        error = error.replace('<', ' ')
        error = error.replace('>', ' ')
        LOGGER.info(self.update.effective_chat.id)
        with download_dict_lock:
            try:
                download = download_dict[self.uid]
                del download_dict[self.uid]
                LOGGER.info(f"Deleting folder: {download.path()}")
                fs_utils.clean_download(download.path())
                LOGGER.info(str(download_dict))
            except Exception as e:
                LOGGER.error(str(e))
                pass
            count = len(download_dict)
        if self.message.from_user.username:
            uname = f"@{self.message.from_user.username}"
        else:
            uname = f'<a href="tg://user?id={self.message.from_user.id}">{self.message.from_user.first_name}</a>'
        msg = f"{uname} your download has been stopped due to: {error}"
        sendMessage(msg, self.bot, self.update)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

    def onUploadStarted(self):
        pass

    def onUploadProgress(self):
        pass

    def onUploadComplete(self, link: str):
        with download_dict_lock:
            msg = f'<a href="{link}">{download_dict[self.uid].name()}</a> ({download_dict[self.uid].size()})'
            LOGGER.info(f'Done Uploading {download_dict[self.uid].name()}')
            if INDEX_URL is not None:
                share_url = requests.utils.requote_uri(f'{INDEX_URL}/{download_dict[self.uid].name()}')
                if os.path.isdir(f'{DOWNLOAD_DIR}/{self.uid}/{download_dict[self.uid].name()}'):
                    share_url += '/'
                msg += f'\n\n Shareable link: <a href="{share_url}">here</a>'
            if self.tag is not None:
                msg += f'\ncc: @{self.tag}'
            try:
                fs_utils.clean_download(download_dict[self.uid].path())
            except FileNotFoundError:
                pass
            del download_dict[self.uid]
            count = len(download_dict)
        sendMessage(msg, self.bot, self.update)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

    def onUploadError(self, error):
        e_str = error.replace('<', '').replace('>', '')
        with download_dict_lock:
            try:
                fs_utils.clean_download(download_dict[self.uid].path())
            except FileNotFoundError:
                pass
            del download_dict[self.uid]
            count = len(download_dict)
        sendMessage(e_str, self.bot, self.update)
        if count == 0:
            self.clean()
        else:
            update_all_messages()


def _mirror(bot: Bot, update: Update, isTar: bool = False, extract: bool = False):
    message_args = update.message.text.split(' ', 3)
    try:
        link = message_args[1]
    except IndexError:
        link = ''
    LOGGER.info(link)
    link = link.strip()
    try:
        options = message_args[2]
    except IndexError:
        options = None

    aria_options = {}
    if options:
        options = options.rsplit(",name=", 1)
        try:
            aria_options.update({"out": options[1]})
        except IndexError:
            pass
        left_options = options[0]
        options = left_options.split(",")
        for option in options:
            option_dict = option.split("=", 1)
            aria_options.update({option_dict[0]:option_dict[1]})

    reply_to = update.message.reply_to_message
    if reply_to is not None:
        file = None
        tag = reply_to.from_user.username
        media_array = [reply_to.document, reply_to.video, reply_to.audio]
        for i in media_array:
            if i is not None:
                file = i
                break

        if len(link) == 0:
            if file is not None:
                if file.mime_type != "application/x-bittorrent":
                    listener = MirrorListener(bot, update, isTar, tag, extract)
                    tg_downloader = TelegramDownloadHelper(listener)
                    tg_downloader.add_download(reply_to, f'{DOWNLOAD_DIR}{listener.uid}/')
                    sendStatusMessage(update, bot)
                    if len(Interval) == 0:
                        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))
                    return
                else:
                    link = file.get_file().file_path
    else:
        tag = None
    if not is_url(link) and not is_magnet(link):
        sendMessage('No download source provided', bot, update)
        return

    try:
        link, cookies = direct_link_generator(link)
        if cookies:
            aria_options.update({"header": f"Cookie:{cookies}"})
    except DirectDownloadLinkException as e:
        LOGGER.info(f'{link}: {e}')
    listener = MirrorListener(bot, update, isTar, tag, extract)
    if is_mega_link(link) and MEGA_KEY is not None:
        mega_dl = MegaDownloader(listener)
        mega_dl.add_download(link, f'{DOWNLOAD_DIR}{listener.uid}/')
    else:
        ariaDlManager.add_download(f'{DOWNLOAD_DIR}/{listener.uid}/', [link], listener, aria_options)
    sendStatusMessage(update, bot)
    if len(Interval) == 0:
        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))


def _mirror_many(bot: Bot, update: Update):
    message_args = update.message.text.split(' ', 2)

    if len(message_args) != 3:
        sendMessage('Usage is : `/mirrormany <single|batch> <link1,link2,link3>`', bot, update, "md")
        return

    mode = message_args[1].strip()
    link = message_args[2].strip()
    LOGGER.info(link)
    tag = None
    
    links = link.split(",")
    invalid_links = []
    valid_links = []
    for each_link in links:
        if not is_url(each_link) and not is_magnet(each_link):
            invalid_links.append(each_link)
        else:
            valid_links.append(each_link)


    if mode == "single":
        num = 1
        for each_link in valid_links:
            listener = MirrorListener(bot, update, False, tag, False)
            listener.uid = f"{listener.uid}{num}"
            ariaDlManager.add_download(f'{DOWNLOAD_DIR}/{listener.uid}/', [each_link], listener, {})
            LOGGER.info(listener.uid)
            num += 1

    elif mode == "batch":
        listener = MirrorListener(bot, update, False, tag, False, f"batch{update.message.message_id}")
        ariaDlManager.add_download(f'{DOWNLOAD_DIR}/{listener.uid}/batch{update.message.message_id}', valid_links, listener, {})

    else:
        sendMessage('Usage is : `/mirror_many <single|batch> <link1,link2,link3>`', bot, update, "md")
        return

    if invalid_links:
        invalid_message = f'{",".join(invalid_links)} are invalid links'
        sendMessage(invalid_message, bot, update)
    sendStatusMessage(update, bot)
    if len(Interval) == 0:
        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))


def mirror(update: Update, context: CallbackContext):
    _mirror(context.bot, update)


def tar_mirror(update: Update, context: CallbackContext):
    _mirror(context.bot, update, True)


def unzip_mirror(update: Update, context: CallbackContext):
    _mirror(context.bot, update, extract=True)


def mirror_many(update: Update, context: CallbackContext):
    _mirror_many(context.bot, update)



mirror_handler = CommandHandler(
    BotCommands.MirrorCommand, mirror,
    CustomFilters.authorized_chat | CustomFilters.authorized_user,
    run_async=True
)
mirror_many_handler = CommandHandler(
    BotCommands.MirrorManyCommand, mirror_many,
    CustomFilters.authorized_chat | CustomFilters.authorized_user,
    run_async=True
)
tar_mirror_handler = CommandHandler(
    BotCommands.TarMirrorCommand, tar_mirror,
    CustomFilters.authorized_chat | CustomFilters.authorized_user,
    run_async=True
)
unzip_mirror_handler = CommandHandler(
    BotCommands.UnzipMirrorCommand, unzip_mirror,
    CustomFilters.authorized_chat | CustomFilters.authorized_user,
    run_async=True
)

dispatcher.add_handler(mirror_handler)
dispatcher.add_handler(mirror_many_handler)
dispatcher.add_handler(tar_mirror_handler)
dispatcher.add_handler(unzip_mirror_handler)
