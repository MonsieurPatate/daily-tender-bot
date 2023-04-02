import logging
import random

from .models import *


class TenderParticipantRepo:
    """
    Репозиторий участников текущего голосования
    """
    @staticmethod
    def add_participants(poll_id: str, members: list[Member]):
        """
        Добавляет новых пользователей как участников текущего голосования.
        :param poll_id: Идентификатор голосования
        :param members: Пользователи, участвующие в голосовании
        """
        logging.info("Adding tender participant for vote (poll_id={0}".format(poll_id))
        for m in members:
            tender_participant = TenderParticipant(poll_id=poll_id, member=m.id, chat_id=m.chat_id)
            tender_participant.save()
            logging.info('Tender participant "{0}" (poll_id={1}) successfully added'.format(
                m.full_name, poll_id))

    @staticmethod
    def get_participants_by_poll_id(poll_id: str):
        """
        Получает информацию об участниках голосования текущего тендера на дейли.
        :param poll_id: Идентификатор голосования
        :return: Список участников текущего тендера
        """
        logging.info(f"Retrieving tender participants...")
        result = TenderParticipant.select().where(TenderParticipant.poll_id == poll_id)
        if len(result) == 0:
            logging.error("Cannot get tender participants: no tender participants in db (poll id={0})".format(poll_id))
            raise DatabaseError("Не найдено участников тендера в базе данных")
        logging.info(f"Retrieved members count: {len(result)}")
        return result

    @staticmethod
    def update_participant_vote_count(poll_id: str, member: Member, vote_count: int):
        """
        Обновляет кол-во голосов за участника.
        :param poll_id: Идентификатор голосования
        :param member: Пользователь, за которого проголосовали
        :param vote_count: Количество голосов
        """
        name = member.full_name
        logging.info("Updating vote count for participant {0} (poll_id={1})".format(name, poll_id))
        poll: TenderParticipant = TenderParticipant.get_or_none(poll_id=poll_id, member_id=member.id)
        if not poll:
            logging.error("Cannot retrieve poll by poll_id={}".format(poll_id))
            raise DatabaseError("Не удаётся получить голосование с id={}".format(poll_id))
        poll.vote_count = vote_count
        poll.save()
        logging.info("Vote count for participant {0} (poll_id={1}) updated successfully".format(name, poll_id))

    @staticmethod
    def get_most_voted_participant(poll_id: str):
        """
        Возвращает участника с наибольшим количеством голосов.
        :param poll_id: Идентификатор голосования
        :return: Участник с наибольшим количеством голосов
        """
        logging.info("Retrieving the most voted participant on poll with id={}".format(poll_id))
        winner: TenderParticipant = (
            TenderParticipant
            .select(TenderParticipant.member, fn.MAX(TenderParticipant.vote_count))
            .where(TenderParticipant.poll_id == poll_id)
            .get_or_none()
        )
        if not winner:
            logging.error("Cannot retrieve most voted participant of daily tender poll (poll_id={})".format(poll_id))
            raise DatabaseError("Не удалось получить победителя тендера на дейли из базы данных (poll_id={})"
                                .format(poll_id))
        logging.info("Most voted participant on poll with id={} successfully retrieved".format(poll_id))
        return winner

    @staticmethod
    def delete_participants(chat_id: int):
        """
        Удаляет участников голосования определенного чата.
        :param chat_id: Идентификатор чата
        """
        logging.info("Deleting participants of closed poll (chat_id={0})".format(chat_id))
        query = TenderParticipant.delete().where(TenderParticipant.chat_id == chat_id)
        result_count = query.execute()
        logging.info("Successfully deleted (chat_id={0}, records={1})".format(chat_id, result_count))


class ConfigRepo:
    """
    Репозиторий конфигураций чатов
    """
    @staticmethod
    def can_organise_daily_poll(chat_id: int) -> bool:
        """
        Возможно ли организовать тендер на дейли.
        :param chat_id: Идентификатор чата
        :return: True - если можно организовать тендер, False - в ином случае
        """
        config = ChatConfig.get_or_none(ChatConfig.chat_id == chat_id)
        logging.info("Configuration of chat #{0} is successfully retrieved".format(chat_id))
        return config.last_daily_date is None or config.last_daily_date < date.today()

    @staticmethod
    def add_config(chat_id: int):
        """
        Добавить конфигурацию чата
        :param chat_id: Идентификатор чата
        """
        config = ChatConfig(chat_id=chat_id)
        res = config.save()
        logging.info("Configuration of chat #{0} is saved ({1})".format(chat_id, res))
        return True

    @staticmethod
    def update_config(chat_id: int,
                      last_daily_date: date = None,
                      last_poll_id: str = None,
                      last_poll_message_id: int = None):
        """
        Обновляет конфигурацию чата.
        :param chat_id: Идентификатор чата
        :param last_daily_date: Дата последнего проведения тендера на дейли
        :param last_poll_id: Идентификатор последнего голосования
        :param last_poll_message_id: Идентификатор сообщения с последним голосованием
        """
        logging.info("Updating configuration of chat with id={}".format(chat_id))
        config: ChatConfig = ChatConfig.get_or_none(chat_id=chat_id)
        if not config:
            logging.error("Cannot retrieve config of chat with id={}".format(chat_id))
            raise DatabaseError('Не удалось получить конфигурацию чата с id={}'.format(chat_id))
        if last_daily_date:
            config.last_daily_date = last_daily_date
        if last_poll_id:
            config.last_poll_id = last_poll_id
        if last_poll_message_id:
            config.last_poll_message_id = last_poll_message_id
        res = config.save()
        logging.info("Configuration of chat #{0} is updated ({1})".format(chat_id, res))

    @staticmethod
    def get_config(chat_id: int):
        """
        Возвращает конфигурацию чата по идентификатору.
        :param chat_id: Идентификатор чата
        :return: Объект чата
        """
        config = ChatConfig.get_or_none(ChatConfig.chat_id == chat_id)
        if not config:
            logging.error('Cannot find config of chat with id "{}"'.format(chat_id))
            raise DatabaseError('Не удалось найти конфигурацию чата с id "{}"'.format(chat_id))
        return config


class MemberRepo:
    """
    Репозиторий пользователей у которых есть возможность участвовать
    в голосовании за проведение дейли
    """
    @staticmethod
    def add_member(full_name: str, chat_id: int):
        """
        Добавляет пользователя для участия в будущих голосованиях
        :param full_name: Имя пользователя
        :param chat_id: Идентификатор чата
        """
        participant, created = Member.get_or_create(full_name=full_name, chat_id=chat_id)
        if not created:
            logging.warning(
                'User with name "{0}" of chat with id={1} is already in database'.format(full_name, chat_id))
            raise DatabaseError('Пользователь "{}" уже есть в базе данных'.format(full_name))
        res = participant.save()
        logging.info('Added new user with name "{0}" ({1})'.format(chat_id, res))

    @staticmethod
    def update_member(chat_id: int,
                      full_name: str,
                      can_participate: bool = None,
                      skip_until_date: date = None):
        """
        Обновляет пользователя чата.
        :param chat_id: Идентификатор чата
        :param full_name: Имя участника
        :param can_participate: Возможность участвовать в дейли
        :param skip_until_date: Дата, до которой пропускается участие в дейли
        """
        logging.info('Updating member with name "{}" of chat with id={}'.format(full_name, chat_id))
        member: Member = Member.get_or_none(chat_id=chat_id, full_name=full_name)
        if not member:
            logging.error('Cannot retrieve member with name "{}" from chat with id={}'.format(full_name, chat_id))
            raise DatabaseError('Не удалось получить участника по имени "{}" чата с id={}'.format(full_name, chat_id))
        if can_participate is not None:
            member.can_participate = can_participate
        member.skip_until_date = skip_until_date
        res = member.save()
        logging.info('Member with name "{}" of chat #{} is updated ({})'.format(full_name, chat_id, res))

    @staticmethod
    def reset_members_participation_statuses(chat_id: int):
        """
        Сбрасывает статус всех участников к дефолтному состоянию "готов к проведению дейли"
        :param chat_id: Идентификатор чата
        """
        logging.info("Resetting member participation status of chat with id={}".format(chat_id))
        query = Member.update(can_participate=True).where(Member.chat_id == chat_id)
        res = query.execute()
        logging.info("Participation statuses of members of chat #{0} is updated (updated {1} rows)"
                     .format(chat_id, res))

    @staticmethod
    def delete_member(identity: str, chat_id: int):
        """
        Удаляет пользователя из участия в будущих голосованиях.
        :param identity: Идентификатор пользователя или имя
        :param chat_id: Идентификатор чата
        """
        identity_label = 'идентификатором' if identity.isdigit() else 'именем'
        participant = Member.get_or_none(Member.identity_query(identity), Member.chat_id == chat_id)
        if not participant:
            logging.error('There is no user with identity "{0}" in database'.format(identity))
            raise DatabaseError('Не удалось удалить пользователя с {} "{}" (нет в базе данных)'
                                .format(identity_label, identity))
        participant.delete_instance()
        logging.info('User with identity "{0}" deleted successfully'.format(identity))

    @staticmethod
    def get_members_by_chat_id(chat_id: int):
        """
        Получает информацию о пользователях чата.
        :param chat_id: Идентификатор чата
        :return: Список пользователей чата
        """
        logging.info(f"Retrieving members...")
        result = Member.select().where(Member.chat_id == chat_id)
        if len(result) == 0:
            logging.error("Cannot get members: no users in db (chat id={0})".format(chat_id))
            raise DatabaseError("Не найдено участников тендера в базе данных")
        logging.info(f"Retrieved members count: {len(result)}")
        return result

    @staticmethod
    def get_member_by_full_name(full_name: str):
        """
        Возвращает пользователя по имени.
        :param full_name: Имя пользователя
        :return: Объект пользователя
        """
        member = Member.get_or_none(Member.full_name == full_name)
        if not member:
            logging.error('Cannot find member by name "{0}"'.format(full_name))
            raise DatabaseError('Не удалось найти пользователя с именем "{0}"'.format(full_name))
        return member

    @staticmethod
    def get_available_members(chat_id: int, count: int = 3, exceptions: list[str] = None):
        """
        Получает список случайно выбранных пользователей для создания голосования.
        :param chat_id: Идентификатор чата
        :param count: Количество участников голосования
        :param exceptions: Имена пользователей, которых не должно быть в выдаче
        :return: Список случайно выбранных пользователей
        """
        logging.info("Retrieving members for daily...")

        if not exceptions:
            exceptions = []

        where_condition = \
            Member.can_participate_query() & (Member.chat_id == chat_id) & (Member.full_name.not_in(exceptions))

        members = Member.select().where(where_condition)

        if len(members) == 0:
            return None

        if len(members) <= count:
            member_names = [m.full_name for m in members]
            logging.info('Got less than {} candidates: {}'.format(count, ' '.join(member_names)))
            return list(members)

        chosen_members: list[Member] = random.sample(list(members), count)
        chosen_member_names = [m.full_name for m in chosen_members]
        logging.info('Successfully chosen members: {0}'.format(' '.join(chosen_member_names)))
        return chosen_members
