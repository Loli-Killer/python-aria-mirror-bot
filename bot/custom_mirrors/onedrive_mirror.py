import re
import json
from time import sleep
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup
from telegram.ext import CommandHandler, run_async

from bot import Interval, LOGGER, dispatcher, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL
from bot.modules.mirror import ariaDlManager, MirrorListener
from bot.helper.ext_utils import bot_utils
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage, update_all_messages


def fetchChildren(fullEncodedPath, cookies, baseUrl, folder=""):

    baseEncodedPath = fullEncodedPath.split(r"%2FDocuments%2F")[0] + r"%2FDocuments"
    topBaseUrl = baseUrl.split("//", 1)[1].split("/", 1)[0]
    headers = {
        'Content-Type': 'application/json'
    }
    fileList = []

    nextUrl = f"https://{topBaseUrl}{unquote(fullEncodedPath.split(r'%2FDocuments%2F')[0])}/_api/web/GetListUsingPath(DecodedUrl=@a1)/RenderListDataAsStream?@a1=%27{baseEncodedPath}%27&RootFolder={fullEncodedPath}&TryNewExperienceSingle=TRUE"
    nextBody = {
        "parameters": {
            "RenderOptions": 5707527,
            "AllowMultipleValueFilterForTaxonomyFields": True,
            "AddRequiredFields": True
        }
    }
    post_r = requests.post(nextUrl, data=json.dumps(nextBody), headers=headers, cookies=cookies).json()
    LOGGER.info("Listing: " + post_r["rootFolder"].rsplit("/", 1)[1])
    fileList += post_r["ListData"]["Row"]
    newData = post_r["ListData"]

    while "NextHref" in newData.keys():
        href = newData["NextHref"][1:]
        nextUrl = f"https://{topBaseUrl}{unquote(fullEncodedPath.split(r'%2FDocuments%2F')[0])}/_api/web/GetListUsingPath(DecodedUrl=@a1)/RenderListDataAsStream?@a1=%27{baseEncodedPath}%27&TryNewExperienceSingle=TRUE&{href}"
        nextBody = {
            "parameters": {
                "RenderOptions": 1216519,
                "ViewXml": "<View Name=\"{56DB6481-F042-4774-9F8B-5535823A23FE}\" DefaultView=\"TRUE\" MobileView=\"TRUE\" MobileDefaultView=\"TRUE\" Type=\"HTML\" ReadOnly=\"TRUE\" DisplayName=\"All\" Url=\"/personal/kimberlysmith_zh_igph_org/Documents/Forms/All.aspx\" Level=\"1\" BaseViewID=\"51\" ContentTypeID=\"0x\" ImageUrl=\"/_layouts/15/images/dlicon.png?rev=47\"><Query><OrderBy><FieldRef Name=\"FileLeafRef\"/></OrderBy></Query><ViewFields><FieldRef Name=\"DocIcon\"/><FieldRef Name=\"LinkFilename\"/><FieldRef Name=\"Modified\"/><FieldRef Name=\"SharedWith\"/><FieldRef Name=\"Editor\"/></ViewFields><RowLimit Paged=\"TRUE\">70</RowLimit><JSLink>clienttemplates.js</JSLink><XslLink Default=\"TRUE\">main.xsl</XslLink><Toolbar Type=\"Standard\"/></View>",
                "AllowMultipleValueFilterForTaxonomyFields": True,
                "AddRequiredFields": True
            }
        }
        post_r = requests.post(nextUrl, data=json.dumps(nextBody), headers=headers, cookies=cookies).json()
        fileList += post_r["ListData"]["Row"]
        newData = post_r["ListData"]
        sleep(0.5)

    dlLinks = []
    for eachFile in fileList:

        isFolder = bool(eachFile[".fileType"])

        if not isFolder:
            newBaseFolder = eachFile["FileRef.urlencode"]
            dlLinks = dlLinks + fetchChildren(newBaseFolder, cookies, baseUrl, folder + "/" + eachFile["FileLeafRef"])
        else:
            dlUrl = baseUrl.split("onedrive.aspx?id=")[0] + "download.aspx?SourceUrl=" + eachFile["FileRef.urlencode"]
            dlLinks.append({
                "fileName": eachFile["FileLeafRef"],
                "filePath": unquote(folder),
                "url": dlUrl
            })
    sleep(0.5)
    return dlLinks


def getCookiesWithPassword(link, password):
    r = requests.get(link)
    soup = BeautifulSoup(r.text, "lxml")
    viewstate = soup.find('input', {'id': '__VIEWSTATE'}).get('value')
    eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'}).get('value')
    linkParts = urlparse(link)
    new_url = f"https://{linkParts.hostname}/personal/{linkParts.path.split('/personal/')[1].split('/')[0]}/_layouts/15/guestaccess.aspx?share={linkParts.path.rsplit('/', 1)[1]}"
    body = {
        "txtPassword": password,
        "__EVENTVALIDATION": eventvalidation,
        "__VIEWSTATE": viewstate,
        "__VIEWSTATEENCRYPTED": ""
    }
    r = requests.post(new_url, data=body)
    return r, f"FedAuth={r.cookies.get_dict()['FedAuth']};"


@run_async
def mirror_onedrive(update, context):

    bot = context.bot
    message_args = update.message.text.split(' ')
    try:
        link = message_args[1]
    except IndexError:
        link = ''

    try:
        password = message_args[2]
    except IndexError:
        password = ''

    try:
        part = message_args[3]
    except IndexError:
        part = ''

    LOGGER.info(link)
    link = link.strip()
    tag = None
    if not bot_utils.is_url(link) and not bot_utils.is_magnet(link):
        sendMessage('No download source provided', bot, update)
        return

    first_r = requests.head(link, allow_redirects=True)

    if "sharepoint.com" in link:
        try:
            cookieString = f"FedAuth={first_r.cookies.get_dict()['FedAuth']};"
        except:
            first_r, cookieString = getCookiesWithPassword(link, password)

        ariaOptions = {
            "header": f"Cookie:{cookieString}"
        }
        if "&parent=" in first_r.url:
            download = first_r.url.split("&parent=")[0]
            download = download.replace("onedrive.aspx?id=", "download.aspx?SourceUrl=")
            listener = MirrorListener(bot, update, False, tag)
            ariaDlManager.add_download(f'{DOWNLOAD_DIR}/{listener.uid}/', [download], listener, ariaOptions)

        else:
            fullEncodedPath = re.search("^.*?id=(.*?)$", first_r.url).group(1)
            rootFolder = unquote(fullEncodedPath.rsplit("%2F", 1)[1])
            childrenItems = fetchChildren(fullEncodedPath, first_r.cookies, first_r.url)

            listener = MirrorListener(bot, update, False, tag, False, rootFolder)
            basePath = f'{DOWNLOAD_DIR}/{listener.uid}/{rootFolder}'
            ariaDlManager.add_download(basePath, childrenItems, listener, ariaOptions, 5, part)


    else:
        download = first_r.history[1].url
        pattern = r".*?resid=(.*?)\!(.*?)\&authkey=(.*?)$"
        result = re.search(pattern, download)
        newUrl = f"https://api.onedrive.com/v1.0/drives/{result.group(1)}/items/{result.group(1)}!{result.group(2)}?select=id%2C%40content.downloadUrl&authkey={result.group(3)}"
        dlUrl = requests.get(newUrl).json()["@content.downloadUrl"]
        
        listener = MirrorListener(bot, update, False, tag)
        ariaDlManager.add_download(f'{DOWNLOAD_DIR}/{listener.uid}/', [dlUrl], listener, {})

    sendStatusMessage(update, bot)
    if len(Interval) == 0:
        Interval.append(bot_utils.setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))


onedrive_handler = CommandHandler("onedrive", mirror_onedrive,
                                filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
dispatcher.add_handler(onedrive_handler)
