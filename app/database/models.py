from peewee import *
from .config import db
from datetime import date


class Member(Model):
    full_name = TextField()
    chat_id = IntegerField()
    skip_until_date = DateField(null=True)
    can_participate = BooleanField(default=True)

    class Meta:
        database = db
        table_name = 'members'

    def get_status_emoji(self):
        if self.skip_until_date and self.skip_until_date > date.today():
            return '⏱'
        return '✅'


class ChatConfig(Model):
    chat_id = IntegerField()
    last_daily_date = DateField(null=True)


    class Meta:
        database = db
        table_name = 'configs'