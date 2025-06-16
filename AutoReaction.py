
# meta developer: @your_username

from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import Message, Channel
from .. import loader, utils

@loader.tds
class AutoReactionMod(loader.Module):
    """Автоматически ставит реакции на новые сообщения в указанных каналах"""

    strings = {
        "name": "AutoReaction",
        "usage": "<b>Использование:</b> .au [ссылка] [реакция]",
        "added": (
            "<b>✅ Реакция добавлена:</b>\n"
            "Канал: <a href='{link}'>{title}</a>\n"
            "Реакция: {reaction}\n"
            "ID авто-реакции: <code>{id}</code>"
        ),
        "no_reactions": "<b>❌ Нет сохраненных автореакций.</b>",
        "list_header": "<b>📋 Список автореакций:</b>\n\n",
        "removed": "<b>🗑️ Автореакция с ID <code>{id}</code> удалена.</b>",
        "not_found": "<b>⚠️ Автореакция с ID <code>{id}</code> не найдена.</b>",
        "invalid_reaction": "<b>❌ Неверная реакция.</b>",
        "joined": "<b>👋 Присоединились к каналу</b>",
        "failed_to_join": "<b>❌ Не удалось присоединиться к каналу</b>",
    }

    strings_ru = {
        "name": "AutoReaction",
        "usage": "<b>Использование:</b> .au [ссылка] [реакция]",
        "added": (
            "<b>✅ Реакция добавлена:</b>\n"
            "Канал: <a href='{link}'>{title}</a>\n"
            "Реакция: {reaction}\n"
            "ID авто-реакции: <code>{id}</code>"
        ),
        "no_reactions": "<b>❌ Нет сохраненных автореакций.</b>",
        "list_header": "<b>📋 Список автореакций:</b>\n\n",
        "removed": "<b>🗑️ Автореакция с ID <code>{id}</code> удалена.</b>",
        "not_found": "<b>⚠️ Автореакция с ID <code>{id}</code> не найдена.</b>",
        "invalid_reaction": "<b>❌ Неверная реакция.</b>",
        "joined": "<b>👋 Присоединились к каналу</b>",
        "failed_to_join": "<b>❌ Не удалось присоединиться к каналу</b>",
    }

    def __init__(self):
        self.reactions = {}  # Хранение реакций
        self.reaction_counter = 0  # Уникальные ID

    async def client_ready(self, client, db):
        self._client = client
        saved = self.get("reactions")
        if saved:
            self.reactions = saved
            self.reaction_counter = max(saved.keys(), default=0)

    async def aucmd(self, message: Message):
        """
        Добавляет авто-реакцию через ссылку.
        Использование: .au [ссылка] [эмодзи или ID]
        """
        args = utils.get_args_raw(message).split(maxsplit=1)
        if len(args) != 2:
            await utils.answer(message, self.strings("usage"))
            return

        url, reaction = args[0], args[1].strip()

        try:
            chat, _ = await self._client.resolve_message_url(url)
        except Exception:
            await utils.answer(message, "<b>❌ Не удалось распознать ссылку.</b>")
            return

        if not isinstance(chat, Channel):
            await utils.answer(message, "<b>❌ Это не канал.</b>")
            return

        # Проверяем, состоите ли вы в канале
        try:
            await self._client.get_participant(chat)
        except Exception:
            try:
                await self._client(JoinChannelRequest(chat))
                await utils.answer(message, self.strings("joined"))
            except Exception:
                await utils.answer(message, self.strings("failed_to_join"))
                return

        chat_id = utils.get_chat_id(chat)
        title = chat.title

        # Обработка реакции
        if reaction.isdigit():
            emoji_id = int(reaction)
            reaction_data = {"custom_emoji_id": str(emoji_id)}
        else:
            reaction_data = {"emoticon": reaction.strip()}

        self.reaction_counter += 1
        rid = self.reaction_counter

        self.reactions[rid] = {
            "chat_id": chat_id,
            "reaction": reaction_data,
        }

        self.set("reactions", self.reactions)

        await utils.answer(
            message,
            self.strings("added").format(
                link=url,
                title=title,
                reaction=reaction.strip(),
                id=rid,
            ),
        )

    async def aulistcmd(self, message: Message):
        """Показывает список всех авто-реакций"""
        if not self.reactions:
            await utils.answer(message, self.strings("no_reactions"))
            return

        res = self.strings("list_header")
        for rid, data in self.reactions.items():
            emoji = (
                data["reaction"]["custom_emoji_id"]
                if "custom_emoji_id" in data["reaction"]
                else data["reaction"]["emoticon"]
            )
            res += f"• ID: <code>{rid}</code>, Чат: <code>{data['chat_id']}</code>, Реакция: {emoji}\n"

        await utils.answer(message, res)

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
        self.set("reactions", self.reactions)
        await utils.answer(message, self.strings("removed").format(id=rid))

    async def watcher(self, message: Message):
        """Ставит реакцию на новые сообщения в отслеживаемых чатах"""
        if not getattr(message, "chat_id", None):
            return

        for rid, data in self.reactions.items():
            if message.chat_id == data["chat_id"]:
                try:
                    await self._client(
                        SendReactionRequest(
                            peer=message.peer_id,
                            msg_id=message.id,
                            big=True,
                            reaction=[data["reaction"]],
                        )
                    )
                except Exception:
                    pass
