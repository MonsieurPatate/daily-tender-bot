from .models import *
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s')


class ConfigRepo:
    @staticmethod
    def add_config(chat_id: int):
        config = ChatConfig(chat_id=chat_id)
        res = config.save()
        logging.info(f"Configuration of chat #{chat_id} is saved ({res})")


class MemberRepo:
    @staticmethod
    def add_participant(full_name: str, chat_id: int):
        participant, created = Member.get_or_create(full_name=full_name, chat_id=chat_id)
        if created:
            res = participant.save()
            logging.info(f'Added new user with name "{full_name}" ({res})')
            return f'Пользователь "{full_name}" успешно добавлен'
        logging.warning(f'User with name "{full_name}" of chat with id={chat_id} is already in database')
        return f'Пользователь "{full_name}" уже есть в базе данных'
    
    @staticmethod
    def delete_participant(identity: str, chat_id: int):
        identity_filter = Member.id == int(identity) if identity.isdigit() else Member.full_name == identity
        identity_label = 'идентификатором' if identity.isdigit() else 'именем'
        participant = Member.get_or_none(identity_filter, Member.chat_id == chat_id)
        if not participant:
            logging.warning(f'There is no user with identity "{identity}" in database')
            return f'Не удалось удалить пользователя с {identity_label} "{identity}" (нет в базе данных)'
        participant.delete_instance()
        logging.info(f'User with identity "{identity}" deleted successfully')
        return f'Пользователь с {identity_label} "{identity}" успешно удалён'
    
    @staticmethod
    def get_participants(chat_id: int):
        logging.info(f"Retrieving users...")
        result = Member.select().where(Member.can_participate & (Member.chat_id == chat_id))
        if len(result) == 0:
            logging.error(f"Cannot get users: no users in db (chat id={chat_id})")
            raise DatabaseError("Не найдено участников тендера в базе данных")
        logging.info(f"Retrieved users count: {len(result)}")
        return result
