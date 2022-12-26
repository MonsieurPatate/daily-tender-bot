from .models import *
import logging
import random

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s')


class TenderParticipantRepo:
    @staticmethod
    def add_participants(poll_id: str, members: list[Member]):
        logging.info("Adding tender participant for vote (poll_id={0}".format(poll_id))
        for m in members:
            tender_participant = TenderParticipant(poll_id=poll_id, member=m, chat_id=m.chat_id)
            tender_participant.save()
            logging.info('Tender participant "{0}" (poll_id={1}) successfully added'.format(
                m.full_name, poll_id))

    @staticmethod
    def update_participant_vote_count(poll_id: str, member: Member, vote_count: int):
        name = member.full_name
        logging.info("Updating vote count for participant {0} (poll_id={1})".format(name, poll_id))
        poll: TenderParticipant = TenderParticipant.get_or_none(poll_id=poll_id, member=member)
        if not poll:
            logging.error("Cannot retrieve poll by poll_id={}".format(poll_id))
        poll.vote_count = vote_count
        poll.save()
        logging.info("Vote count for participant {0} (poll_id={1}) updated successfully".format(name, poll_id))

    @staticmethod
    def get_most_voted_participant(poll_id: str):
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
        logging.info("Deleting participants of closed poll (chat_id={0})".format(chat_id))
        query = TenderParticipant.delete().where(TenderParticipant.chat_id == chat_id)
        result_count = query.execute()
        logging.info("Successfully deleted (chat_id={0}, records={1})".format(chat_id, result_count))


class ConfigRepo:
    @staticmethod
    def can_organise_daily_poll(chat_id: int) -> bool:
        config = ChatConfig.get_or_none(ChatConfig.chat_id == chat_id)
        logging.info("Configuration of chat #{0} is successfully retrieved".format(chat_id))
        return config.last_daily_date is None or config.last_daily_date < date.today()

    @staticmethod
    def add_config(chat_id: int):
        config = ChatConfig(chat_id=chat_id)
        res = config.save()
        logging.info("Configuration of chat #{0} is saved ({1})".format(chat_id, res))
        return True

    @staticmethod
    def update_config(chat_id: int, last_daily_date: date = None):
        logging.info("Updating configuration of chat with id={}".format(chat_id))
        config: ChatConfig = ChatConfig.get_or_none(chat_id=chat_id)
        if not config:
            logging.error("Cannot retrieve config of chat with id={}".format(chat_id))
            raise DatabaseError('Не удалось получить конфигурацию чата с id={}'.format(chat_id))
        if last_daily_date:
            config.last_daily_date = last_daily_date
        res = config.save()
        logging.info("Configuration of chat #{0} is updated ({1})".format(chat_id, res))


class MemberRepo:
    @staticmethod
    def add_member(full_name: str, chat_id: int):
        participant, created = Member.get_or_create(full_name=full_name, chat_id=chat_id)
        if created:
            res = participant.save()
            logging.info('Added new user with name "{0}" ({1})'.format(chat_id, res))
            return f'Пользователь "{full_name}" успешно добавлен'
        logging.warning('User with name "{0}" of chat with id={1} is already in database'.format(full_name, chat_id))
        return f'Пользователь "{full_name}" уже есть в базе данных'

    @staticmethod
    def reset_member_participation_status(chat_id: int):
        logging.info("Resetting member participation status of chat with id={}".format(chat_id))
        query = Member.update(can_participate=True).where(Member.chat_id == chat_id)
        res = query.execute()
        logging.info("Participation statuses of members of chat #{0} is updated (updated {1} rows)"
                     .format(chat_id, res))

    @staticmethod
    def delete_member(identity: str, chat_id: int):
        identity_filter = Member.id == int(identity) if identity.isdigit() else Member.full_name == identity
        identity_label = 'идентификатором' if identity.isdigit() else 'именем'
        participant = Member.get_or_none(identity_filter, Member.chat_id == chat_id)
        if not participant:
            logging.warning('There is no user with identity "{0}" in database'.format(identity))
            return f'Не удалось удалить пользователя с {identity_label} "{identity}" (нет в базе данных)'
        participant.delete_instance()
        logging.info('User with identity "{0}" deleted successfully'.format(identity))
        return f'Пользователь с {identity_label} "{identity}" успешно удалён'

    @staticmethod
    def get_members(chat_id: int):
        logging.info(f"Retrieving members...")
        result = Member.select().where(Member.chat_id == chat_id)
        if len(result) == 0:
            logging.error("Cannot get members: no users in db (chat id={0})".format(chat_id))
            raise DatabaseError("Не найдено участников тендера в базе данных")
        logging.info(f"Retrieved members count: {len(result)}")
        return result

    @staticmethod
    def get_member_by_full_name(full_name: str):
        member = Member.get_or_none(Member.full_name == full_name)
        if not member:
            logging.error('Cannot find member by name "{0}"'.format(full_name))
            raise DatabaseError('Не удалось найти пользователя с именем "{0}"'.format(full_name))
        return member

    @staticmethod
    def get_members_for_daily(chat_id: int, count: int = 3):
        logging.info("Retrieving members for daily...")
        member_count = Member.select().where(Member.can_participate_query() & (Member.chat_id == chat_id)).count()

        if member_count == 0:
            logging.warning("No members in db that can participate on daily tender (chat id={0}), resetting members..."
                            .format(chat_id))
            MemberRepo.reset_member_participation_status(chat_id)
        else:
            logging.info("{} members can participate".format(member_count))

        members = Member.select().where(Member.can_participate_query() & (Member.chat_id == chat_id))

        if len(members) == 0:
            logging.error("Cannot get members: no users in db that can participate on daily tender (chat id={0})")
            raise DatabaseError('Не удалось получить пользователей для создания опроса')

        if len(members) <= 3:
            member_names = [m.full_name for m in members]
            logging.info('Got less than three candidates: {0}'.format(' '.join(member_names)))
            return list(members), member_names

        chosen_members: list[Member] = random.sample(list(members), count)
        chosen_member_names = [m.full_name for m in chosen_members]
        logging.info('Successfully chosen members: {0}'.format(' '.join(chosen_member_names)))
        return chosen_members, chosen_member_names
