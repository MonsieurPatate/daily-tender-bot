import os
import sys
import telebot

current_dir = os.path.dirname(os.path.realpath(__file__))
main_folder_path = os.path.dirname(current_dir)
parent_dir = os.path.dirname(main_folder_path)
sys.path.append(os.path.dirname(parent_dir))
sys.path.append(current_dir)
sys.path.append(parent_dir)
sys.path.append(main_folder_path)

from app.config import db
from app.orm_models.models import Member, ChatConfig, TenderParticipant
from bot import bot


if __name__ == '__main__':
    db.create_tables([Member, ChatConfig, TenderParticipant])
    bot.set_my_commands([
        telebot.types.BotCommand("/start", "Запуск бота"),
        telebot.types.BotCommand("/add", "Добавление пользователей"),
        telebot.types.BotCommand("/delete", "Удаление пользователей"),
        telebot.types.BotCommand("/info", "Список участников тендера"),
        telebot.types.BotCommand("/poll", "Создание тендера на проведение дейли"),
        telebot.types.BotCommand("/repoll", "Замена одного участника текущего опроса"),
        telebot.types.BotCommand("/endpoll", "Завершение опроса"),
    ])

    # Start the bot
    bot.polling(non_stop=True, interval=0)
