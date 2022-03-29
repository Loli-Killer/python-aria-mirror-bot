import os
import sys
import shlex
import random
import itertools
import threading
import binascii
from pathlib import Path
from time import sleep, time

import irc.client

from bot import LOGGER, download_dict, download_dict_lock
from bot.helper.ext_utils.bot_utils import MirrorStatus, genpacks
from bot.helper.mirror_utils.status_utils.xdcc_status import XDCCDownloadStatus


irc.client.ServerConnection.buffer_class.encoding = "latin-1"


def random_nickname(word="lolikiller"):
    """Return a randomly chosen anagram of the word supplied."""
    choices = itertools.permutations(word)
    choices = list(choices)
    return "".join(random.choice(choices))


class XDCCArgs:

    def __init__(self, _dict):

        self.bot = _dict['bot']
        self.server = _dict['server']
        self.port = _dict['port']
        self.channel = "#" + str(_dict['channel'])
        self.action = _dict['action']
        self.packs = _dict['packs'].strip("#")
        self.stdout = False


class XDCCDownload(irc.client.SimpleIRCClient):
    """This class implements a simple IRC client that connect to the specified server
    and channel(if any) to finally ask for a XDCC bot to send the requested file
    represented by the pack number passed on the command line options.

    Args:
        args(parser.args): The command-line arguments
    """

    def __init__(self, listener):
        super().__init__()
        self.__listener = listener
        self.args = None
        self.packs_iter = None
        self.pack_length = 0
        self.base_path = ""

        self.file = None
        self.__name = None
        self.__status_text = None
        self.__status = MirrorStatus.STATUS_DOWNLOADING
        self.__current_pack = 0
        self.last_pack = 0
        self.percentage = 0
        self.speed = 0
        self.received_bytes = 0
        self.total_size = 0
        self.last_received_bytes = 0
        self.last_print_time = 0

        self.end_loop = False
        self.cancelled = False

    @property
    def progress(self):
        return self.percentage

    @property
    def downloaded_bytes(self):
        return self.received_bytes

    @property
    def size(self):
        return self.total_size

    @property
    def gid(self):
        return format(binascii.crc32((self.args.bot + self.args.packs).encode('utf8')), '08x')

    @property
    def name(self):
        if not self.__name:
            return self.gid
        if self.pack_length != 1:
            fullname = f"{self.__name} [{self.__current_pack}/{self.pack_length}]"
        else:
            fullname = f"{self.__name}"
        return fullname

    @property
    def download_speed(self):
        return self.speed

    @property
    def status(self):
        if self.__status_text:
            return self.__status + self.__status_text
        return self.__status


    def on_welcome(self, c, e):
        """This is called when we are welcomed by the IRC server."""
        LOGGER.debug("Welcome page of the server was reached successfully.")
        if self.args.channel:
            self.requested = False
            self.connection.join(self.args.channel)
        else:
            self.request_file_to_bot()


    def on_join(self, c, e):
        """Called when we successfully joined the channel."""
        # Some channels can trigger this function multiple times
        LOGGER.debug("Joined to channel %s.", self.args.channel)
        if not self.requested:
            self.request_file_to_bot()
            self.requested = True


    def request_file_to_bot(self):
        """Sends a ctcp message to the bot requesting the pack number specified
        on the command-line arguments.

        When the send action was chosen, this method raise StopIteration when there is
        no more pack to be downloaded.
        """
        LOGGER.debug("Sending command to the bot...")
        if self.args.action == "list":
            self.connection.ctcp("xdcc", self.args.bot, "send list")
        elif self.args.action == "send":
            next_pack = next(self.packs_iter)
            self.connection.ctcp(
                "xdcc", self.args.bot, "send %d" % next_pack
            )
            self.last_pack = next_pack
            self.__current_pack += 1


    def on_ctcp(self, connection, event):
        """Method called when a ctcp message has arrived.

        For more information on the connection and event arguments
        see the documentation for irc.client.SimpleIRCClient
        """
        LOGGER.debug("CTCP: %s", event.arguments)
        if event.arguments[0] != "DCC":
            return

        payload = event.arguments[1]
        parts = shlex.split(payload)
        command, filename, peer_address, peer_port, size = parts
        if command != "SEND":
            return

        self.__name = os.path.basename(filename)
        self.filename = os.path.join(self.base_path, self.__name)
        self.file = sys.stdout if self.args.stdout else open(self.filename, "wb")
        self.start_time = time()

        self.total_size = int(size)

        # Reset some important information
        self.received_bytes = 0
        self.last_received_bytes = 0
        self.last_print_time = 0

        peer_address = irc.client.ip_numstr_to_quad(peer_address)
        peer_port = int(peer_port)
        self.current_dcc_connection = self.dcc_connect(peer_address, peer_port, "raw")


    def on_privnotice(self, connection, event):
        if event.arguments[0] == "** You already requested that pack":
            wait_time = 60
            while wait_time != 0:
                self.__status = MirrorStatus.STATUS_RETRYING
                self.__status_text = f" in {wait_time}s"
                self.update_download_status()
                if self.end_loop:
                    break
                self.reactor.process_once(0.2)
                sleep(1)
                wait_time = wait_time - 1
            if self.end_loop:
                self.connection.quit()
            else:
                self.connection.ctcp(
                    "xdcc", self.args.bot, "send %d" % self.last_pack
                )
                self.__status = MirrorStatus.STATUS_DOWNLOADING
                self.__status_text = None


    def on_dccmsg(self, connection, event):
        """Receive a DCC msg block from the bot."""
        # Apparently the bots that i have used to test are both using the TURBO DCC instead
        # of the standard DCC.
        data = event.arguments[0]
        self.file.write(data.decode("utf-8") if self.args.stdout else data)
        self.received_bytes = self.received_bytes + len(data)

        # Since we are assuming a TURBO DCC transference, let close the connection when
        # the file has been completely transmitted.
        if self.received_bytes == self.total_size:
            self.current_dcc_connection.disconnect()

        self.update_download_status()


    def update_download_status(self):
        """Show the download status interactively on the screen. Information such as
        filename, total transferred(in percentage), network speed and estimated time are
        currently shown.
        """
        if self.__status == MirrorStatus.STATUS_DOWNLOADING:
            self.elapsed_time = time() - self.start_time
            self.percentage = 100 * self.received_bytes / self.total_size
            self.speed = self.received_bytes / self.elapsed_time
            self.last_received_bytes = self.received_bytes


    def on_dcc_disconnect(self, connection, event):
        """This is called when the bot disconnect the DCC comunication."""
        LOGGER.debug("DCC connection closed by remote peer!")
        self.file.close()

        if self.args.action == "send":
            try:
                self.request_file_to_bot()
            except StopIteration:
                self.connection.quit()
        else:  # list
            self.connection.quit()


    def on_disconnect(self, connection, event):
        """Called when disconnecting from the server."""
        LOGGER.debug("Disconnected!")
        self.end_loop = True


    def process_until_break(self, timeout=0.2):
        """Custom process_forever."""
        while True:
            self.reactor.process_once(timeout)
            if self.end_loop:
                break
        if self.cancelled:
            if self.file:
                self.file.close()
            self.connection.quit()
            self.__listener.onDownloadError('Cancelled by user')
        else:
            self.__listener.onDownloadComplete()


    def __onDownloadStart(self):
        with download_dict_lock:
            download_dict[self.__listener.uid] = XDCCDownloadStatus(self, self.__listener)
        self.__listener.onDownloadStarted()


    def add_download(self, args, path, nickname=None):
        Path(path).mkdir(parents=True, exist_ok=True)
        self.base_path = path
        self.args = XDCCArgs(args)
        self.pack_length = sum(1 for _ in genpacks(self.args.packs))
        self.packs_iter = genpacks(self.args.packs)

        if not nickname:
            nickname = random_nickname()

        if self.args.action == "batch":
            self.args.action = "send"

        try:
            self.connect(self.args.server, self.args.port, nickname)
        except irc.client.ServerConnectionError as e:
            self.__listener.onDownloadError(e)
            return

        (threading.Thread(target=self.process_until_break)).start()
        self.__onDownloadStart()
        LOGGER.info(f'Started xdcc download for {self.args.packs} from bot {self.args.bot}')


    def cancel_download(self):
        LOGGER.info(f'Cancelling download on user request: {self.gid}')
        self.end_loop = True
        self.cancelled = True
