from peewee import *
from .config import db
from datetime import date


class Member(Model):
    full_name = TextField()
    chat_id = IntegerField()
    skip_until_date = DateField(null=True)
    can_participate = BooleanField(null=True, default=True)

    class Meta:
        database = db
        table_name = 'members'

    def get_status_emoji(self):
        if self.skip_until_date and self.skip_until_date > date.today() or self.can_participate:
            return '✅'
        return '⏱'

    @staticmethod
    def can_participate_query():
        return (Member.skip_until_date < date.today()) | (
                (Member.skip_until_date == None) & (Member.can_participate == True))


class ChatConfig(Model):
    chat_id = IntegerField(unique=True)
    last_daily_date = DateField(null=True)

    class Meta:
        database = db
        table_name = 'configs'


class TenderParticipant(Model):
    poll_id = TextField()
    chat_id = IntegerField()
    vote_count = IntegerField(default=0)
    member = ForeignKeyField(Member)

    class Meta:
        database = db
        table_name = 'tender_participants'
