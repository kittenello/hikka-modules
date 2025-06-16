
# meta developer: @your_username


import asyncio
import logging
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.types import Channel, Message
from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class AutoReactionMod(loader.Module):
    """Автоматически ставит реакции на новые сообщения в указанных каналах."""

    strings = {
        "name": "AutoReaction",
        "usage": "<b>Использование:</b> .au [@канал/ID] [реакция]",
        "added": (
            "<b>✅ Реакция добавлена:</b>\n"
            "Канал: <code>{chat}</code>\n"
            "Реакция: {reaction}\n"
            "ID авто-реакции: <code>{id}</code>"
        ),
        "no_reactions": "<b>❌ Нет сохраненных автореакций.</b>",
        "list_header": "<b>📋 Список автореакций:</b>\n\n",
        "removed": "<b>🗑️ Автореакция с ID <code>{id}</code> удалена.</b>",
        "not_found": "<b>⚠️ Автореакция с ID <code>{id}</code> не найдена.</b>",
        "invalid_reaction": "<b>❌ Неверная реакция.</b>",
    }

    strings_ru = {
        "usage": "<b>Использование:</b> .au [@канал/ID] [реакция]",
        "added": (
            "<b>✅ Реакция добавлена:</b>\n"
            "Канал: <code>{chat}</code>\n"
            "Реакция: {reaction}\n"
            "ID авто-реакции: <code>{id}</code>"
        ),
        "no_reactions": "<b>❌ Нет сохраненных автореакций.</b>",
        "list_header": "<b>📋 Список автореакций:</b>\n\n",
        "removed": "<b>🗑️ Автореакция с ID <code>{id}</code> удалена.</b>",
        "not_found": "<b>⚠️ Автореакция с ID <code>{id}</code> не найдена.</b>",
        "invalid_reaction": "<b>❌ Неверная реакция.</b>",
    }

    def __init__(self):
        self.reactions = {}
        self.reaction_counter = 0

    async def aucmd(self, message: Message):
        """
        Добавляет авто-реакцию.
        Использование: .au [@канал/ID] [реакция]
        """
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings("usage"))
            return

        try:
            chat_input, reaction = args.split(maxsplit=1)
        except ValueError:
            await utils.answer(message, self.strings("usage"))
            return

        try:
            chat = await self._client.get_entity(chat_input)
        except Exception as e:
            logger.error(f"Ошибка получения чата: {e}")
            await utils.answer(message, "<b>❌ Не удалось найти канал/чат.</b>")
            return

        chat_id = utils.get_chat_id(chat)

        if not reaction or len(reaction.strip()) == 0:
            await utils.answer(message, self.strings("invalid_reaction"))
            return

        self.reaction_counter += 1
        reaction_id = self.reaction_counter

        self.reactions[reaction_id] = {
            "chat_id": chat_id,
            "reaction": reaction.strip(),
        }

        await utils.answer(
            message,
            self.strings("added").format(
                chat=chat_input,
                reaction=reaction.strip(),
                id=reaction_id,
            ),
        )

    async def aulistcmd(self, message: Message):
        """Показывает список всех активных авто-реакций"""
        if not self.reactions:
            await utils.answer(message, self.strings("no_reactions"))
            return

        response = self.strings("list_header")
        for rid, data in self.reactions.items():
            response += f"• ID: <code>{rid}</code>, Чат: <code>{data['chat_id']}</code>, Реакция: {data['reaction']}\n"

        await utils.answer(message, response)

    async def audcmd(self, message: Message):
        """Удаляет авто-реакцию по ID"""
        args = utils.get_args_raw(message)
        if not args.isdigit():
            await utils.answer(message, "<b>❌ Укажите числовой ID.</b>")
            return

        rid = int(args)
        if rid not in self.reactions:
            await utils.answer(message, self.strings("not_found").format(id=rid))
            return

        del self.reactions[rid]
        await utils.answer(message, self.strings("removed").format(id=rid))

    async def watcher(self, message: Message):
        """Ставит реакцию, если сообщение из отслеживаемого чата"""
        if not isinstance(message, Message) or not message.chat_id:
            return

        for rid, data in self.reactions.items():
            if message.chat_id == data["chat_id"]:
                try:
                    await self._client(SetTypingRequest(
                        peer=message.chat_id,
                        action=data["reaction"]
                    ))
                except Exception as e:
                    logger.warning(f"Не удалось поставить реакцию: {e}")
