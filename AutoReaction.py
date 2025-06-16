# meta developer: @kolyankid

__version__ = (1, 0, 0)

from .. import loader, utils
from telethon.tl.types import Message, ReactionEmoji, ReactionCustomEmoji
import asyncio

@loader.tds
class AutoReactionMod(loader.Module):
    """Автоматически ставит реакции на сообщения в указанных чатах"""
    strings = {
        "name": "AutoReaction",
        "added": "<b>✅ Реакция добавлена</b>\n\nChat: {}\nReaction: {}\nID: {}",
        "removed": "<b>🗑️ Реакция удалена</b>\nID: {}",
        "no_reaction": "<b>❌ Не указано, какую реакцию ставить</b>",
        "not_in_chat": "<b>❌ Я не состою в этом чате</b>",
        "invalid_id": "<b>❌ Неверный ID реакции</b>",
        "list_title": "<b>📌 Список авто-реакций:</b>\n",
        "no_reactions": "<b>❌ Нет активных реакций</b>",
        "log_channel_created": "<b>💬 Лог-канал создан: heroku-autoreaction</b>",
    }

    def __init__(self):
        self.reactions = {}
        self.log_chat = None
        self._reaction_id = 1

    async def client_ready(self, client, db):
        self.db = db
        self._log_chat, _ = await utils.asset_channel(
            client,
            "heroku-autoreaction",
            "📦 Логи авто-реакций",
            silent=True,
            invite_bot=True,
            _folder="hikka"
        )
        self.log_chat = f"-100{self._log_chat.id}"
        saved = self.db.get("AutoReaction", "reactions", {})
        self.reactions = saved
        self._reaction_id = max(saved.keys(), default=0) + 1

    def save_reactions(self):
        self.db.set("AutoReaction", "reactions", self.reactions)

    async def aucmd(self, message: Message):
        """
        .au [@канал/ID канала] [эмодзи или custom_emoji_id]
        Добавляет авто-реакцию на сообщения в указанном чате
        """
        args = utils.get_args_raw(message).split(maxsplit=1)
        if len(args) < 2:
            return await utils.answer(message, self.strings["no_reaction"])

        try:
            chat_input = args[0]
            reaction_input = args[1]

            chat = await self._client.get_entity(chat_input)
            chat_id = utils.get_chat_id(chat)

            if reaction_input.isdigit():
                reaction = ReactionCustomEmoji(document_id=int(reaction_input))
            else:
                reaction = ReactionEmoji(emoticon=reaction_input)

            self.reactions[self._reaction_id] = {
                "chat_id": chat_id,
                "reaction": reaction,
            }

            self.save_reactions()

            await utils.answer(
                message,
                self.strings["added"].format(
                    chat.title,
                    reaction_input,
                    self._reaction_id
                )
            )

            await self._client.send_message(
                self.log_chat,
                f"🆕 Добавлена авто-реакция:\nChat: {chat.title} ({chat_id})\nReaction: {reaction_input}\nID: {self._reaction_id}"
            )

            self._reaction_id += 1

        except Exception as e:
            await utils.answer(message, f"<b>❌ Ошибка:</b> {e}")

    async def aulistcmd(self, message: Message):
        """Вывести список авто-реакций"""
        if not self.reactions:
            return await utils.answer(message, self.strings["no_reactions"])

        output = self.strings["list_title"]
        for rid, data in self.reactions.items():
            chat = await self._client.get_entity(data["chat_id"], ignore_error=True)
            title = chat.title if chat else data["chat_id"]
            emoji = data["reaction"].emoticon if isinstance(data["reaction"], ReactionEmoji) else str(data["reaction"].document_id)
            output += f"• <code>{rid}</code>: {title} → {emoji}\n"

        await utils.answer(message, output)

    async def audcmd(self, message: Message):
        """Удалить авто-реакцию по ID"""
        args = utils.get_args_raw(message)
        if not args or not args.isdigit():
            return await utils.answer(message, self.strings["invalid_id"])

        rid = int(args)
        if rid not in self.reactions:
            return await utils.answer(message, self.strings["invalid_id"])

        del self.reactions[rid]
        self.save_reactions()
        await utils.answer(message, self.strings["removed"].format(rid))

        await self._client.send_message(
            self.log_chat,
            f"🗑️ Удалена авто-реакция с ID: {rid}"
        )

    async def watcher(self, message: Message):
        if not isinstance(message, Message):
            return

        chat_id = utils.get_chat_id(message)

        for rid, data in self.reactions.items():
            if data["chat_id"] == chat_id:
                try:
                    await self._client.send_reaction(
                        chat_id,
                        message.id,
                        data["reaction"]
                    )
                except Exception as e:
                    await self._client.send_message(
                        self.log_chat,
                        f"⚠️ Ошибка при установке реакции в {chat_id}: {e}"
                    )