from telebot import TeleBot
from database.repo import MemberRepo
from database.config import db
import logging

bot_token = '5806300117:AAHRdpP_8SF-Mw1UM9xBi3omSwBSneRt9fs'
bot = TeleBot(bot_token)


def extract_arg(arg: str) -> list[str]:
    args = arg.split()[1:]
    if len(args) == 0:
        logging.error(f"Отсутствуют аргументы для команды")
        raise ValueError('Отсутствуют аргументы команды')


@bot.message_handler(commands=["start"])
def start(message):
    logging.debug(type(message))
    bot.send_message(message.chat.id, 'Я на связи. Напиши мне что-нибудь )')


@bot.message_handler(commands=["add"])
def add(message):
    with db.atomic() as transaction:
        try:
            args: list[str] = extract_arg(message.text)
            chat_id = message.chat.id
            name = ' '.join(args)
            result_message = MemberRepo.add_participant(full_name=name, chat_id=chat_id)
            bot.send_message(message.chat.id, result_message)
        except Exception as e:
            transaction.rollback()
            bot.send_message(message.chat.id, f"Произошла ошибка при добавлении пользователя: {e}")


@bot.message_handler(commands=["delete"])
def delete(message):
    with db.atomic() as transaction:
        try:
            args: list[str] = extract_arg(message.text)
            name = ' '.join(args)
            chat_id = message.chat.id
            result_message = MemberRepo.delete_participant(full_name=name, chat_id=chat_id)
            bot.send_message(message.chat.id, result_message)
        except Exception as e:
            transaction.rollback()
            bot.send_message(message.chat.id, f"Произошла ошибка при удалении пользователя: {e}")


@bot.message_handler(commands=["chatinfo"])
def chat_info(message):
    with db.atomic() as transaction:
        try:
            chat_id = message.chat.id
            members = MemberRepo.get_participants(chat_id=chat_id)
            res = f'Встречайте участников тендера:\n'
            i = 0
            for member in members:
                i += 1
                res += f'{i}. {member.get_status_emoji()} {member.full_name} (id={member.id})\n'
            bot.send_message(chat_id, res)
        except Exception as e:
            transaction.rollback()
            bot.send_message(message.chat.id, f"Произошла ошибка при получении пользователей: {e}")
