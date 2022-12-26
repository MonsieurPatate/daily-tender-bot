import telebot

from app.database.config import db
from app.database.models import Member, ChatConfig, TenderParticipant
from bot import bot

if __name__ == '__main__':
    # db.drop_tables([Member, ChatConfig, TenderParticipant])
    db.create_tables([Member, ChatConfig, TenderParticipant])
    bot.set_my_commands([
        telebot.types.BotCommand("/start", "Запуск бота"),
        telebot.types.BotCommand("/add", "Добавление пользователей"),
        telebot.types.BotCommand("/delete", "Удаление пользователей"),
        telebot.types.BotCommand("/info", "Список участников тендера"),
    ])

    # Запускаем бота
    bot.polling(none_stop=True, interval=0)
