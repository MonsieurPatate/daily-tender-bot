import telebot

from bot import bot


if __name__ == '__main__':

    bot.set_my_commands([
        telebot.types.BotCommand("/start", "Запуск бота"),
        telebot.types.BotCommand("/add", "Добавление пользователей"),
        telebot.types.BotCommand("/delete", "Удаление пользователей"),
        telebot.types.BotCommand("/chatinfo", "Список участников тендера"),
    ])

    # Запускаем бота
    bot.polling(none_stop=True, interval=0)
