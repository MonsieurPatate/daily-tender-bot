import logging
from datetime import date, timezone, datetime
from threading import Thread
from time import sleep

from telebot import TeleBot
from telebot.types import Poll, PollOption

from app import constants
from app.constants import default_daily_hours, default_daily_minutes
from app.database.models import Member
from database.config import db, bot_token, scheduler
from database.repo import MemberRepo, ConfigRepo, TenderParticipantRepo

bot = TeleBot(bot_token)


def get_today_time_utc(hours: int, minutes: int):
    """
    Возвращает сегодняшнюю дату по UTC с конкретным временем (часы и минуты).
    :param hours: Часы
    :param minutes: Минуты
    :return: Объект времени
    """
    return datetime.now(tz=timezone.utc).replace(hour=hours, minute=minutes, second=0)


def extract_arg(arg: str, count: int = None, zero_args: bool = False) -> list[str] | None:
    """
    Получает аргументы команды бота.
    :param arg: Строка, включающая команду и аргументы вида '/command arg1 arg2'
    :param count: Кол-во аргументов
    :param zero_args: Может быть 0 аргументов
    :return: Список аргументов без самой команды, либо None, если не получилось спарсить
    аргументы
    """
    args = arg.split()[1:]

    if len(args) == 0 and zero_args:
        return None

    if count and len(args) != count:
        logging.error("Cannot parse command args (arg={}). Count of args should be {}".format(arg, count))
        raise ValueError('Отсутствуют аргументы команды (строка - "{}"). Должно быть аргументов: {}'.format(arg, count))

    return args


def schedule_checker():
    """
    Проверяет и запускает отложенные задачи. Запускать в отдельном потоке.
    """
    logging.info('Start of schedule loop to execute jobs on separate thread')
    while len(scheduler.get_jobs()) > 0:
        scheduler.exec_jobs()
        sleep(1)
    logging.info('Schedule loop shut down successfully')


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
            bot.send_message(chat_id, constants.win_message.format(winner.full_name))
            winner.can_participate = False
            winner.save()
        except Exception as e:
            transaction.rollback()
            bot.send_message(chat_id, f"Произошла ошибка при получении результатов голосования: {e}")


def set_schedule(time: datetime, chat_id: int, poll_id: str):
    """
    Создаёт отложенную задачу в отдельном потоке. Удаляет до этого созданные
    задачи.
    :param time: Время
    :param chat_id: Идентификатор чата
    :param poll_id: Идентификатор голосования
    :return:
    """
    logging.info("Setting schedule to check poll results to time (UTC): {}"
                 .format(time.strftime('%d/%m/%Y %H:%M:%S')))
    scheduler.delete_jobs()
    scheduler.once(time, check_poll_results, kwargs={"chat_id": chat_id, 'poll_id': poll_id})
    Thread(target=schedule_checker).start()


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
    Удаляет пользователя. В сообщении после команды должно быть имя или id пользователя.
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
    В случае отсутствия аргумента времени будет установлено время по умолчанию (6:25 UTC)
    :param message: Сообщение с командой
    """
    sent_message = None
    with db.atomic() as transaction:
        try:
            args: list[str] = extract_arg(message.text)
            if args:
                hours, minutes = args[0], args[1]
                if not (hours.isdigit() and minutes.isdigit()):
                    raise ValueError('Время задано неверно: {} {}'.format(hours, minutes))
                hours, minutes = int(hours), int(minutes)
            else:
                hours, minutes = default_daily_hours, default_daily_minutes

            chat_id = message.chat.id

            if not ConfigRepo.can_organise_daily_poll(chat_id):
                logging.error('Cannot organise daily tender in chat (id={}): there was already a daily tender today'
                              .format(chat_id))
                raise Exception('сегодня уже был тендер на дейли')

            participants, participant_names = MemberRepo.get_members_for_daily(chat_id=chat_id)

            if len(participants) == 1:
                logging.info("Got just one participant available, poll is not necessary")
                winner = participants[0]
                bot.send_message(chat_id, constants.win_message.format(winner.full_name))
                winner.can_participate = False
                winner.save()
                return

            sent_message = bot.send_poll(chat_id=chat_id,
                                         options=participant_names,
                                         question=constants.poll_header)

            poll_id = sent_message.poll.id
            TenderParticipantRepo.delete_participants(chat_id)
            TenderParticipantRepo.add_participants(poll_id, participants)

            set_schedule(time=get_today_time_utc(hours, minutes),
                         chat_id=chat_id,
                         poll_id=poll_id)

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
