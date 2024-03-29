import logging
import re
from datetime import date, timedelta
from time import sleep

from telebot.types import Poll, PollOption
from app import constants
from app.config import db, scheduler, bot
from app.orm_models.models import Member, ChatConfig, TenderParticipant
from app.utils import set_schedule, get_daily_time_utc, check_poll_results, extract_args, \
    get_members_for_daily, get_correct_poll_time, try_parse_date
from orm_models.repo import MemberRepo, ConfigRepo, TenderParticipantRepo


def send_remaining_member_win_message(chat_id, winner, delete_jobs: bool = False):
    """
    В случае, когда остаётся последний участник, который может проводить дейли,
    отправляет сообщение о победе этого человека без создания голосования. При необходимости
    удаляет отложенные задачи (отправка победителя голосования с посчётом голосов).
    :param chat_id: Идентификатор чата
    :param winner: Победивший пользователь
    :param delete_jobs: Удалять ли отложенные задачи
    :return:
    """
    logging.info("Got just one participant available, poll is not necessary")
    bot.send_message(chat_id, constants.WIN_MESSAGE_TEMPLATE.format(winner.full_name))
    MemberRepo.update_member(chat_id, winner.full_name, can_participate=False)
    if delete_jobs:
        scheduler.delete_jobs()


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
            bot.send_message(chat_id, f"Произошла ошибка при создании первичной конфигурации чата: {e}")


def schedule_checker():
    """
    Проверяет и запускает отложенные задачи. Запускать в отдельном потоке.
    """
    logging.info('Start of schedule loop to execute jobs on separate thread')
    while len(scheduler.get_jobs()) > 0:
        scheduler.exec_jobs()
        sleep(1)
    logging.info('Schedule loop shut down successfully')


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
            bot.send_message(message.chat.id, f"Произошла ошибка при добавлении первичной конфигурации бота: {e}")


@bot.message_handler(commands=["add"])
def add(message):
    """
    Добавляет пользователя. В сообщении после команды должно быть имя пользователя.
    :param message: Сообщение с командой
    """
    with db.atomic() as transaction:
        try:
            chat_id = message.chat.id
            name = extract_args(message.text, 1)[0].replace('"', '')
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
            identity = extract_args(message.text, 1)[0].replace('"', '')
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
            members = MemberRepo.get_members_by_chat_id(chat_id=chat_id)
            res = 'Встречайте участников тендера:\n'
            for index, member in enumerate(list(members), 1):
                res += f'{index}. {member.get_status_emoji()} {member.full_name} ' \
                       f'(id={member.id}{member.availability_info()})\n'
            bot.send_message(chat_id, res)
        except Exception as e:
            transaction.rollback()
            bot.send_message(message.chat.id, f"Произошла ошибка при получении пользователей: {e}")


@bot.message_handler(commands=["free"])
def free(message):
    """
    Освобождает пользователя от участия в тендерах до указанной даты
    :param message: Сообщение с командой
    """
    with db.atomic() as transaction:
        try:
            chat_id = message.chat.id
            args: list[str] = extract_args(message.text, 2)
            full_name = args[0].replace('"', '')
            parsed_date = try_parse_date(args[1])
            MemberRepo.update_member(chat_id=chat_id,
                                     full_name=full_name,
                                     skip_until_date=parsed_date)
            bot.send_message(chat_id, f"{full_name} освобождён от тендеров до {parsed_date.strftime('%d.%m.%Y')}")
        except Exception as e:
            transaction.rollback()
            bot.send_message(chat_id, f"Ошибка исполнения команды: {e}")


@bot.message_handler(commands=["poll"])
def create_poll(message):
    """
    Запускает голосование из трёх случайно выбранных пользователей на указанное время.
    В сообщении после команды должно быть время окончания голосования.
    В случае отсутствия аргумента времени будет установлено время по умолчанию (6:25 UTC)
    :param message: Сообщение с командой
    """
    sent_message = None
    with db.atomic() as transaction:
        try:
            chat_id = message.chat.id
            time_str = extract_args(message.text, 1)[0]
            args: list[str] = re.split('[:.]', time_str)
            hours, minutes, warning = constants.DEFAULT_DAILY_HOURS, constants.DEFAULT_DAILY_MINUTES, None

            if args:
                hours, minutes, warning = get_correct_poll_time(args[0], args[1])

            if warning:
                bot.send_message(chat_id, warning)

            if not ConfigRepo.can_organise_daily_poll(chat_id):
                logging.error('Cannot organise daily tender in chat (id={}): there was already a daily tender today'
                              .format(chat_id))
                raise Exception('сегодня уже был тендер на дейли')

            members = get_members_for_daily(chat_id)

            if len(members) == 1:
                winner = members[0]
                send_remaining_member_win_message(chat_id, winner)
                return

            options = [m.full_name for m in members]
            sent_message = bot.send_poll(chat_id=chat_id,
                                         options=options,
                                         question=constants.POLL_HEADER)

            poll_id = sent_message.poll.id
            TenderParticipantRepo.delete_participants(chat_id)
            TenderParticipantRepo.add_participants(poll_id, members)

            daily_time = get_daily_time_utc(hours, minutes)
            set_schedule(time=daily_time, chat_id=chat_id)

            ConfigRepo.update_config(chat_id=chat_id,
                                     last_daily_date=date.today(),
                                     last_poll_id=poll_id,
                                     last_poll_message_id=sent_message.id)
        except Exception as e:
            transaction.rollback()
            if sent_message:
                bot.delete_message(chat_id, sent_message.id)
            bot.send_message(message.chat.id, f"Произошла ошибка при создании опроса: {e}")


@bot.message_handler(commands=["repoll"])
def recreate_poll(message):
    """
    Перезапускает голосование. Убирает из предыдущего голосования одного человека
    по имени из аргумента команды (/repoll <имя человека>). Заменяет человека рандомно
    на другого, у которого есть возможность проводить дейли.
    :param message: Сообщение с командой
    """
    sent_message = None
    with db.atomic() as transaction:
        try:
            chat_id: int = message.chat.id

            config: ChatConfig = ConfigRepo.get_config(chat_id)
            if config.is_poll_not_relevant():
                logging.error('Cannot recreate poll that does not exist')
                raise Exception('Не удаётся пересоздать опрос без предварительного создания')

            dropped_member_name: str = extract_args(message.text, 1)[0].replace('"', '')

            logging.info('Recreating poll, dropping member with name "{}" and choosing new tender participant'
                         .format(dropped_member_name))

            tender_participants: list[TenderParticipant] = TenderParticipantRepo.get_participants_by_poll_id(
                config.last_poll_id
            )

            old_tender_member_names: list[str] = list(map(lambda x: x.member.full_name, tender_participants))

            if dropped_member_name not in old_tender_member_names:
                raise ValueError('Среди участников текущего голосования нет пользователя с именем {}'
                                 .format(dropped_member_name))

            new_tender_members: list[Member] = list(filter(
                lambda x: x.full_name != dropped_member_name,
                map(lambda x: x.member, tender_participants)
            ))

            new_random_member_sample = MemberRepo.get_available_members(chat_id, 1, old_tender_member_names)
            if new_random_member_sample:
                new_tender_members.append(new_random_member_sample[0])

            new_tender_member_names = list(map(lambda x: x.full_name, new_tender_members))

            MemberRepo.update_member(chat_id=chat_id,
                                     full_name=dropped_member_name,
                                     skip_until_date=date.today() + timedelta(days=1))

            if len(new_tender_member_names) == 1:
                winner = new_tender_members[0]
                send_remaining_member_win_message(chat_id, winner, True)
                return

            sent_message = bot.send_poll(chat_id=chat_id,
                                         options=new_tender_member_names,
                                         question=constants.POLL_HEADER)

            poll_id = sent_message.poll.id
            TenderParticipantRepo.delete_participants(chat_id)
            TenderParticipantRepo.add_participants(poll_id, new_tender_members)

            ConfigRepo.update_config(chat_id,
                                     last_poll_id=poll_id,
                                     last_poll_message_id=sent_message.id)
            bot.delete_message(chat_id, config.last_poll_message_id)

        except Exception as e:
            transaction.rollback()
            if sent_message:
                bot.delete_message(chat_id, sent_message.id)
            bot.send_message(message.chat.id, f"Произошла ошибка при пересоздании опроса: {e}")


@bot.poll_handler(lambda poll: not poll.is_closed)
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
            for option in options:
                member = MemberRepo.get_member_by_full_name(option.text)
                TenderParticipantRepo.update_participant_vote_count(poll_id, member, option.voter_count)
            logging.info('Successfully updated vote counts of daily tender poll (poll_id={0})'.format(poll_id))
        except Exception as e:
            transaction.rollback()


@bot.message_handler(commands=["endpoll"])
def end_poll(message):
    chat_id = message.chat.id

    config: ChatConfig = ConfigRepo.get_config(chat_id)
    if config.is_poll_not_relevant():
        logging.error('Cannot end poll that does not exist')
        bot.send_message(chat_id, 'Не удаётся завершить опрос без предварительного создания')
        return

    logging.info("Premature closing of poll in chat (id={})".format(chat_id))
    scheduler.delete_jobs()
    check_poll_results(chat_id)
    logging.info("Poll in chat (id={}) successfully closed".format(chat_id))
