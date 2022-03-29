import threading
from time import sleep, time

from aria2p import API

from bot import aria2, LOGGER, download_dict, download_dict_lock
from bot.helper.ext_utils.bot_utils import new_thread, is_magnet, getDownloadByGid, genpacks
from bot.helper.mirror_utils.download_utils.download_helper import DownloadHelper
from bot.helper.mirror_utils.status_utils.aria_download_status import AriaDownloadStatus
from bot.helper.telegram_helper.message_utils import update_all_messages


class AriaQueue:

    def __init__(self, base_path, listener, links, aria_options, delayTime, partsToDownload):
        self.listener = listener
        self.name = ""

        self.queue = (link for link in links)
        self.queue_length = len(links)
        self.current_download = 0
        self.download_index = 0

        self.base_path = base_path
        self.aria_options = aria_options

        self.delayTime = delayTime
        self.lastRunTime = 0

        self.partsToDownload = genpacks(f"1-{self.queue_length}")
        if partsToDownload:
            self.queue_length = len([length for length in genpacks(partsToDownload)])
            self.partsToDownload = genpacks(partsToDownload)


class AriaDownloadHelper(DownloadHelper):

    def __init__(self):
        super().__init__()
        self.queue_dict = {}

    def CustomName(self, uid):
        queue = self.queue_dict[uid]
        if queue.queue_length != 1:
            return queue.name, f"[{queue.current_download}/{queue.queue_length}]"
        else:
            return queue.name, None


    @new_thread
    def __onDownloadStarted(self, api, gid):
        LOGGER.info(f"onDownloadStart: {gid}")
        dl = getDownloadByGid(gid)
        if dl:
            self.queue_dict[dl.uid()].name = api.get_download(gid).name
        update_all_messages()


    def __onDownloadComplete(self, api: API, gid):
        LOGGER.info(f"onDownloadComplete: {gid}")
        dl = getDownloadByGid(gid)
        download = api.get_download(gid)
        if download.followed_by_ids:
            new_gid = download.followed_by_ids[0]
            new_download = api.get_download(new_gid)
            with download_dict_lock:
                download_dict[dl.uid()] = AriaDownloadStatus(new_gid, dl.getListener(), self)
                if new_download.is_torrent:
                    download_dict[dl.uid()].is_torrent = True
            update_all_messages()
            LOGGER.info(f'Changed gid from {gid} to {new_gid}')
            return
        if dl:
            queue = self.queue_dict[dl.uid()]
            if queue.current_download != queue.queue_length:
                self.__startNextDownload(dl.uid())
                return
            threading.Thread(target=dl.getListener().onDownloadComplete).start()


    @new_thread
    def __onDownloadPause(self, api, gid):
        LOGGER.info(f"onDownloadPause: {gid}")
        dl = getDownloadByGid(gid)
        try:
            dl.getListener().onDownloadError('Download stopped by user!')
        except AttributeError:
            pass


    @new_thread
    def __onDownloadStopped(self, api, gid):
        LOGGER.info(f"onDownloadStop: {gid}")
        dl = getDownloadByGid(gid)
        if dl:
            dl.getListener().onDownloadError('Download stopped by user!')


    @new_thread
    def __onDownloadError(self, api, gid):
        sleep(0.5) #sleep for split second to ensure proper dl gid update from onDownloadComplete
        LOGGER.info(f"onDownloadError: {gid}")
        dl = getDownloadByGid(gid)
        download = api.get_download(gid)
        error = download.error_message
        LOGGER.info(f"Download Error: {error}")
        if dl:
            dl.getListener().onDownloadError(error)


    def start_listener(self):
        aria2.listen_to_notifications(
            threaded=True,
            on_download_start=self.__onDownloadStarted,
            on_download_error=self.__onDownloadError,
            on_download_pause=self.__onDownloadPause,
            on_download_stop=self.__onDownloadStopped,
            on_download_complete=self.__onDownloadComplete
        )


    def __startNextDownload(self, uid):

        queue = self.queue_dict[uid]
        entry = next(queue.queue)
        queue.current_download += 1
        queue.download_index += 1
        aria_options = queue.aria_options

        try:
            nextPart = next(queue.partsToDownload)
        except StopIteration:
            threading.Thread(target=queue.listener.onDownloadComplete).start()
            return
        
        while nextPart > queue.download_index:
            entry = next(queue.queue)
            queue.download_index += 1

        if queue.delayTime:
            currentTime = time()
            if queue.lastRunTime:
                waitTime = currentTime - queue.lastRunTime
                if waitTime < queue.delayTime:
                    sleep(waitTime)

            queue.lastRunTime = currentTime

        if isinstance(entry, dict):
            aria_options.update({'dir': queue.base_path + entry["filePath"]})
            if 'file_name' in entry.keys():
                aria_options.update({'out': entry['fileName']})
            link = entry['url']
        else:
            aria_options.update({'dir': queue.base_path})
            link = entry

        if is_magnet(link):
            download = aria2.add_magnet(link, aria_options)
        else:
            download = aria2.add_uris([link], aria_options)

        if download.error_message:
            queue.listener.onDownloadError(download.error_message)
            return

        with download_dict_lock:
            download_dict[queue.listener.uid] = AriaDownloadStatus(download.gid, queue.listener, self)

        LOGGER.info(f"Started: {download.gid} DIR:{download.dir} ")


    def add_download(
        self,
        base_path: str,
        links,
        listener,
        aria_options: dict = {},
        delayTime: int = 0,
        partsToDownload: str = ""
    ):

        self.queue_dict[listener.uid] = AriaQueue(base_path, listener, links, aria_options, delayTime, partsToDownload)
        self.__startNextDownload(listener.uid)
