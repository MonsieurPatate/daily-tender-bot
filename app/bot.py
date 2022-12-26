import logging
from datetime import date
from threading import Thread
from time import sleep

import schedule
from telebot import TeleBot
from telebot.types import Poll, PollOption

from app import constants
from app.database.models import Member
from database.config import db, bot_token
from database.repo import MemberRepo, ConfigRepo, TenderParticipantRepo

bot = TeleBot(bot_token)


def extract_arg(arg: str) -> list[str]:
    """
    Получает аргументы команды бота.
    :param arg: Строка, включающая команду и аргументы вида '/command arg1 arg2'
    :return: Список аргументов без самой команды
    """
    args = arg.split()[1:]
    if len(args) == 0:
        logging.error(f"Cannot parse command args (arg={arg})")
        raise ValueError('Отсутствуют аргументы команды')
    return args


def schedule_checker():
    """
    Проверяет и запускает отложенные задачи. Запускать в отдельном потоке.
    """
    while True:
        schedule.run_pending()
        sleep(1)


def check_poll_results(chat_id: int, poll_id: str):
    """
    Вызывается как отложенный метод, выполняет проверку результатов
    голосования на проведение дейли.
    :param chat_id: Идентификатор чата
    :param poll_id: Идентификатор голосования
    """
    with db.atomic() as transaction:
        try:
            winner: Member = TenderParticipantRepo.get_most_voted_participant(poll_id).member
            send_winner_message(chat_id, winner)
            return schedule.CancelJob
        except Exception as e:
            transaction.rollback()
            bot.send_message(chat_id, f"Произошла ошибка при получении результатов голосования: {e}")


def send_winner_message(chat_id, winner):
    """
    Отправляет строку с указанием победителя
    в голосовании на проведение дейли.
    :param chat_id: Идентификатор чата
    :param winner: Объект победителя голосования
    """
    bot.send_message(chat_id, constants.win_message.format(winner.full_name))
    winner.can_participate = False
    winner.save()


@bot.message_handler(commands=["start"])
def start(message):
    """
    Проводит первичную инициализацию конфигурации чата.
    :param message: Сообщение с командой
    """
    with db.atomic() as transaction:
        try:
            chat_id = message.chat.id
            ConfigRepo.add_config(chat_id=chat_id)
            bot.send_message(chat_id, 'Добавлена первичная конфигурация бота для этого чата')
        except Exception as e:
            transaction.rollback()
            bot.send_message(message.chat.id,
                             f"Произошла ошибка при добавлении первичной конфигурации бота: {e}")


@bot.message_handler(commands=["add"])
def add(message):
    """
    Добавляет пользователя. В сообщении после команды должно быть имя пользователя.
    :param message: Сообщение с командой
    """
    with db.atomic() as transaction:
        try:
            args: list[str] = extract_arg(message.text)
            chat_id = message.chat.id
            name = ' '.join(args)
            MemberRepo.add_member(full_name=name, chat_id=chat_id)
            bot.send_message(message.chat.id, 'Пользователь "{}" успешно добавлен'.format(name))
        except Exception as e:
            transaction.rollback()
            bot.send_message(message.chat.id, f"Произошла ошибка при добавлении пользователя: {e}")


@bot.message_handler(commands=["delete"])
def delete(message):
    """
    Удаляет пользователя. В сообщении после команды должно быть имя пользователя.
    :param message: Сообщение с командой
    """
    with db.atomic() as transaction:
        try:
            args: list[str] = extract_arg(message.text)
            identity = ' '.join(args)
            chat_id = message.chat.id
            MemberRepo.delete_member(identity=identity, chat_id=chat_id)
            bot.send_message(message.chat.id, 'Пользователь с идентификатором "{}" успешно удалён'
                             .format(identity))
        except Exception as e:
            transaction.rollback()
            bot.send_message(message.chat.id, f"Произошла ошибка при удалении пользователя: {e}")


@bot.message_handler(commands=["info"])
def chat_info(message):
    """
    Отправляет информацию об пользователях их доступности для участия в голосовании.
    :param message: Сообщение с командой
    :return:
    """
    with db.atomic() as transaction:
        try:
            chat_id = message.chat.id
            members = MemberRepo.get_members(chat_id=chat_id)
            res = 'Встречайте участников тендера:\n'
            for i, member in enumerate(list(members), 1):
                res += f'{i}. {member.get_status_emoji()} {member.full_name} (id={member.id})\n'
            bot.send_message(chat_id, res)
        except Exception as e:
            transaction.rollback()
            bot.send_message(message.chat.id, f"Произошла ошибка при получении пользователей: {e}")


@bot.message_handler(commands=["poll"])
def vote(message):
    """
    Запускает голосование из трёх случайно выбранных пользователей на указанное время.
    В сообщении после команды должно быть время окончания голосования.
    :param message: Сообщение с командой
    """
    sent_message = None
    with db.atomic() as transaction:
        try:
            args: list[str] = extract_arg(message.text)
            time = args[0]
            chat_id = message.chat.id

            if not ConfigRepo.can_organise_daily_poll(chat_id):
                logging.error('Cannot organise daily tender in chat (id={}): there was already a daily tender today'
                              .format(chat_id))
                raise Exception('сегодня уже был тендер на дейли')

            participants, participant_names = MemberRepo.get_members_for_daily(chat_id=chat_id)

            if len(participants) == 1:
                logging.info("Got just one participant available, poll is not necessary")
                send_winner_message(chat_id, participants[0])
                return

            sent_message = bot.send_poll(chat_id=chat_id,
                                         options=participant_names,
                                         question=constants.poll_header)

            poll_id = sent_message.poll.id
            TenderParticipantRepo.delete_participants(chat_id)
            TenderParticipantRepo.add_participants(poll_id, participants)

            schedule.every().day.at(time).do(check_poll_results, chat_id=chat_id, poll_id=poll_id)
            Thread(target=schedule_checker).start()

            ConfigRepo.update_config(chat_id, last_daily_date=date.today())
        except Exception as e:
            transaction.rollback()
            if sent_message:
                bot.delete_message(chat_id, sent_message.id)
            bot.send_message(message.chat.id, f"Произошла ошибка при создании опроса: {e}")


@bot.poll_handler(lambda p: not p.is_closed)
def vote_answer_handler(poll: Poll):
    """
    Хэндлер, реагирующий на выборы в голосовании. Записывает голоса
    участников голосования в БД.
    :param poll: Объект голосования
    """
    with db.atomic() as transaction:
        try:
            poll_id: str = poll.id
            logging.info('Updating vote counts of daily tender poll (poll_id={0})'.format(poll_id))
            options: list[PollOption] = poll.options
            for o in options:
                member = MemberRepo.get_member_by_full_name(o.text)
                TenderParticipantRepo.update_participant_vote_count(poll_id, member, o.voter_count)
            logging.info('Successfully updated vote counts of daily tender poll (poll_id={0})'.format(poll_id))
        except Exception as e:
            transaction.rollback()
