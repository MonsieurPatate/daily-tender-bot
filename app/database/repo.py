from .models import *
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s')


class ConfigRepo:
    @staticmethod
    def add_config(chat_id: int):
        config = ChatConfig(chat_id=chat_id)
        res = config.save()
        logging.info(f"Конфигурация чата #{chat_id} сохранена ({res})")


class MemberRepo:
    @staticmethod
    def add_participant(full_name: str, chat_id: int):
        participant, created = Member.get_or_create(full_name=full_name, chat_id=chat_id)
        if created:
            res = participant.save()
            logging.info(f'Новый пользователь "{full_name}" сохранён ({res})')
            return f'Пользователь "{full_name}" успешно добавлен'
        logging.warning(f'Пользователь "{full_name}" чата id={chat_id} уже существует в базе данных')
        return f'Пользователь "{full_name}" уже есть в базе данных'
    
    @staticmethod
    def delete_participant(full_name: str, chat_id: int):
        identity_filter = Member.id == int(full_name) if full_name.isdigit() else Member.full_name == full_name
        identity_label = 'идентификатором' if full_name.isdigit() else 'именем'
        participant = Member.get_or_none(identity_filter, Member.chat_id == chat_id)
        if not participant:
            logging.warning(f'Пользователь с {identity_label} "{full_name}" не найден в базе данных')
            return f'Не удалось удалить пользователя с {identity_label} "{full_name}" (нет в базе данных)'
        participant.delete_instance()
        logging.info(f'Пользователь с {identity_label} "{full_name}" успешно удалён')
        return f'Пользователь с {identity_label} "{full_name}" успешно удалён'
    
    @staticmethod
    def get_participants(chat_id: int):
        logging.info(f"Получение пользователей")
        result = Member.select().where(Member.is_participant & (Member.chat_id == chat_id))
        if len(result) == 0:
            logging.error(f"Не найдено участников тендера в базе данных (chatid={chat_id})")
            raise DatabaseError("Не найдено участников тендера в базе данных")
        logging.info(f"Получено пользователей: {len(result)}")
        return result
