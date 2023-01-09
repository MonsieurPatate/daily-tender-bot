from datetime import date

from peewee import *

from .config import db


class Member(Model):
    """
    Класс пользователя-участника в будущих голосованиях
    за проведение дейли
    """
    full_name = TextField()
    chat_id = IntegerField()
    skip_until_date = DateField(null=True)
    can_participate = BooleanField(null=True, default=True)

    class Meta:
        database = db
        table_name = 'members'

    def get_status_emoji(self):
        """
        Возвращает эмодзи-статус доступности пользователя
        для голосования.
        :return: Строка со статусом в виде эмодзи
        """
        if self.__is_not_available():
            return '⏱'
        return '✅'

    def availability_info(self):
        """
        Возвращает информацию, проводил ли участник дейли в
        текущей итерации, а также дату с которой он будет учавствовать в дейли
        :return: Строка со статусом в виде эмодзи
        """
        if not self.can_participate:
            return ', уже провёл дейли'
        if self.__is_not_available() and self.skip_until_date is not None:
            return self.skip_until_date.strftime(", доступен с %d.%m.%Y")

        return ''

    def __is_not_available(self):
        """
        Возвращает True, если участник доступен для участия в розыгрыше
        тендера на дейли
        :return: True - участник доступен, иначе - False
        """
        return self.skip_until_date and self.skip_until_date > date.today() or not self.can_participate

    @staticmethod
    def identity_query(identity: str):
        return Member.id == int(identity) if identity.isdigit() else Member.full_name == identity

    @staticmethod
    def can_participate_query():
        """
        Возвращает запрос в бд о возможности участия в дейли.
        :return: Запросо о возможности участия в дейли
        """
        return (Member.skip_until_date < date.today()) | (
                (Member.skip_until_date == None) & (Member.can_participate == True))


class ChatConfig(Model):
    """
    Конфигурация чата
    """
    chat_id = IntegerField(unique=True)
    last_daily_date = DateField(null=True)
    last_poll_id = TextField(null=True)
    last_poll_message_id = IntegerField(null=True)

    def is_poll_not_relevant(self):
        return self.last_daily_date is None or self.last_daily_date != date.today()

    class Meta:
        database = db
        table_name = 'configs'


class TenderParticipant(Model):
    """
    Участник текущего голосования за право проведения дейли
    """
    poll_id = TextField()
    chat_id = IntegerField()
    vote_count = IntegerField(default=0)
    member = ForeignKeyField(Member)

    class Meta:
        database = db
        table_name = 'tender_participants'
