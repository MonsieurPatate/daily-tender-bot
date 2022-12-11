import telebot

bot = telebot.TeleBot('5654314334:AAHAFbzp1UtYz3qclDneNTfNAQYUMe3VQ80')


# Функция, обрабатывающая команду /start
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id, 'Я на связи. Напиши мне что-нибудь )')
