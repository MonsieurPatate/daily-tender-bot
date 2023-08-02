import os
import telebot

from datetime import timezone
from peewee import *
from scheduler import Scheduler

bot_token = os.environ["BOT_TOKEN"]

bot = telebot.TeleBot(bot_token)
db = SqliteDatabase(
        os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                'database',
                'main.db'
        )
)
scheduler = Scheduler(tzinfo=timezone.utc, n_threads=0)
