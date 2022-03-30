import time

from telegram import Message, Update, Bot

from bot import AUTO_DELETE_MESSAGE_DURATION, LOGGER, bot, \
    status_reply_dict, status_reply_dict_lock
from bot.helper.ext_utils.bot_utils import get_readable_message


def sendMessage(text: str, bot: Bot, update: Update, mode: str = "HTML"):
    try:
        if mode == "HTML":
            return bot.send_message(
                update.message.chat_id,
                reply_to_message_id=update.message.message_id,
                text=text, parse_mode='HTML'
            )
        elif mode == "md":
            return bot.send_message(
                update.message.chat_id,
                reply_to_message_id=update.message.message_id,
                text=text, parse_mode='Markdown'
            )
    except Exception as e:
        LOGGER.error(str(e))


def editMessage(text: str, message: Message, message_group: dict = None):
    try:
        if message_group:
            bot.edit_message_text(
                text=text, message_id=message_group["message_id"],
                chat_id=message_group["chat_id"],
                parse_mode='HTML'
            )
        else:
            bot.edit_message_text(
                text=text, message_id=message.message_id,
                chat_id=message.chat.id,
                parse_mode='HTML'
            )
    except Exception as e:
        LOGGER.error(str(e))


def deleteMessage(bot: Bot, message: Message):
    try:
        bot.delete_message(
            chat_id=message.chat.id,
            message_id=message.message_id
        )
    except Exception as e:
        LOGGER.error(str(e))


def sendLogFile(bot: Bot, update: Update):
    with open('log.txt', 'rb') as f:
        bot.send_document(
            document=f, filename=f.name,
            reply_to_message_id=update.message.message_id,
            chat_id=update.message.chat_id
        )


def auto_delete_message(bot: Bot, cmd_message: Message, bot_message: Message):
    if AUTO_DELETE_MESSAGE_DURATION != -1:
        time.sleep(AUTO_DELETE_MESSAGE_DURATION)
        try:
            # Skip if None is passed meaning we don't want to delete bot xor cmd message
            deleteMessage(bot, cmd_message)
            deleteMessage(bot, bot_message)
        except AttributeError:
            pass


def delete_all_messages():
    with status_reply_dict_lock:
        for message in list(status_reply_dict.values()):
            try:
                deleteMessage(bot, message)
                del status_reply_dict[message.chat.id]
            except Exception as e:
                LOGGER.error(str(e))


def update_all_messages():
    msg = get_readable_message()
    with status_reply_dict_lock:
        for chat_id in list(status_reply_dict.keys()):
            if status_reply_dict[chat_id] and msg != status_reply_dict[chat_id].text:
                try:
                    msg = msg[:2048]
                    editMessage(msg, status_reply_dict[chat_id])
                except Exception as e:
                    LOGGER.error(str(e))
                status_reply_dict[chat_id].text = msg


def sendStatusMessage(msg: Message, bot: Bot):
    progress = get_readable_message()
    with status_reply_dict_lock:
        if msg.message.chat.id in list(status_reply_dict.keys()):
            try:
                message = status_reply_dict[msg.message.chat.id]
                deleteMessage(bot, message)
                del status_reply_dict[msg.message.chat.id]
            except Exception as e:
                LOGGER.error(str(e))
                del status_reply_dict[msg.message.chat.id]
                pass
        message = sendMessage(progress, bot, msg)
        status_reply_dict[msg.message.chat.id] = message
