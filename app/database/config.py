import os
from datetime import timezone, datetime

from peewee import *
from scheduler import Scheduler

db = SqliteDatabase('main.db')
scheduler = Scheduler(tzinfo=timezone.utc, n_threads=0)
daily_time = datetime(year=2022, month=12, day=28, hour=3, minute=33, tzinfo=timezone.utc)

bot_token = os.environ["BOT_TOKEN"]