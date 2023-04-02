import logging
from datetime import datetime, timezone
from threading import Thread
from time import sleep

from peewee import DatabaseError

from app import constants
from app.config import scheduler, bot, db
from app.constants import default_daily_hours, default_daily_minutes
from app.orm_models.models import ChatConfig, Member
from app.orm_models.repo import ConfigRepo, TenderParticipantRepo, MemberRepo


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


def get_string_after_command(message_text: str):
    """
    Возвращает строку после команды (/command <строка>)
    :param message_text: текст с командой и аргументами
    :return: Строка после команды
    """
    logging.info('Getting identity from command "{}"'.format(message_text))
    args: list[str] = extract_arg(message_text)
    joined_str_arg = ' '.join(args)
    if not joined_str_arg:
        logging.error('Error during parsing identity: empty identity string')
        raise ValueError('Ошибка ввода команды: после команды необходимо ввести хотя бы один символ')
    return joined_str_arg


def get_daily_time_utc(hours: int, minutes: int):
    """
    Возвращает сегодняшнюю дату по UTC с конкретным временем (часы и минуты).
    :param hours: Часы
    :param minutes: Минуты
    :return: Объект времени
    """
    now = datetime.now(tz=timezone.utc)
    daily_time = now.replace(hour=hours, minute=minutes, second=0)
    if daily_time < now:
        daily_time_str = daily_time.strftime('%H:%M')
        now_str = now.strftime('%H:%M')
        raise ValueError('Время дейли должно быть задано '
                         'после текущего времени (время={} по UTC, сейчас={} по '
                         'UTC)'.format(daily_time_str, now_str))
    return daily_time


def schedule_checker():
    """
    Проверяет и запускает отложенные задачи. Запускать в отдельном потоке.
    """
    logging.info('Start of schedule loop to execute jobs on separate thread')
    while len(scheduler.get_jobs()) > 0:
        scheduler.exec_jobs()
        sleep(1)
    logging.info('Schedule loop shut down successfully')


def check_poll_results(chat_id: int):
    """
    Вызывается как отложенный метод, выполняет проверку результатов
    голосования на проведение дейли.
    :param chat_id: Идентификатор чата
    """
    with db.atomic() as transaction:
        try:
            config: ChatConfig = ConfigRepo.get_config(chat_id=chat_id)
            poll_id: str = config.last_poll_id
            winner: Member = TenderParticipantRepo.get_most_voted_participant(poll_id).member
            bot.send_message(chat_id, constants.win_message.format(winner.full_name))
            MemberRepo.update_member(chat_id=chat_id, full_name=winner.full_name, can_participate=False)
        except Exception as e:
            transaction.rollback()
            bot.send_message(chat_id, f"Произошла ошибка при получении результатов голосования: {e}")


def get_members_for_daily(chat_id):
    """
    Возвращает трёх доступных для голосования участников
    тендера на дейли. В случае отсутствия доступных участников
    сбрасывает статус доступности участия у пользователей.
    :param chat_id: Идентификатор чата
    :return: Кандидаты на голосование
    """
    members = MemberRepo.get_available_members(chat_id=chat_id)
    if members is None:
        logging.warning("No members in db that can participate "
                        "on daily tender (chat id={0}), resetting members..."
                        .format(chat_id))
        MemberRepo.reset_members_participation_statuses(chat_id)
        members = MemberRepo.get_available_members(chat_id=chat_id)
        if members is None:
            logging.error("Cannot get members: no users in db that "
                          "can participate on daily tender (chat id={})".format(chat_id))
            raise DatabaseError('Не удалось получить пользователей для создания опроса')
    else:
        logging.info("{} members can participate".format(len(members)))
    return members


def set_schedule(time: datetime, chat_id: int):
    """
    Создаёт отложенную задачу в отдельном потоке. Удаляет до этого созданные
    задачи.
    :param time: Время
    :param chat_id: Идентификатор чата
    :return:
    """
    logging.info("Setting schedule to check poll results to time (UTC): {}"
                 .format(time.strftime('%d/%m/%Y %H:%M:%S')))
    scheduler.once(time, check_poll_results, kwargs={"chat_id": chat_id})
    Thread(target=schedule_checker).start()


def get_correct_poll_time(hours_str: str, minutes_str: str):
    """
    Возвращает корректное время (два целых числа: часы и минуты) из аргументов команды. В случае
    неудачного парсинга времени возвращает значения по умолчанию и сообщение об ошибке.
    :param hours_str: Строка с часами
    :param minutes_str: Строка с минутами
    :return: Два целых числа: часы и минуты, а также строка с ошибкой (None в случае отсутствия ошибок)
    """
    if hours_str.isdigit() and minutes_str.isdigit():
        hours, minutes = int(hours_str), int(minutes_str)
        return hours, minutes, None
    else:
        logging.warning("Got time in wrong format (hours={}, minutes={}). All args should be digits."
                        .format(hours_str, minutes_str))
        logging.info("Setting default time UTC (hours={}, minutes={}) for scheduling daily poll"
                     .format(default_daily_hours, default_daily_minutes))
        warning = 'Не удалось установить дейли в указанное время (часы={}, минуты={}). Голосование установлено на '\
                  'время по умолчанию ({}:{} UTC)'.format(hours_str,
                                                          minutes_str,
                                                          default_daily_hours,
                                                          default_daily_minutes)
        return default_daily_hours, default_daily_minutes, warning


def try_parse_date(date_string):
    """
    Возвращает дату, сформированную из строки
    :param date_string: Строкое представление даты
    :return: Дата
    """
    for date_format in ('%d.%m.%Y', '%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d%m%Y', '%Y%m%d'):
        try:
            return datetime.strptime(date_string, date_format).date()
        except ValueError:
            pass
    raise ValueError('no valid date format found')
