from telethon import events, types
from .. import loader, utils
import logging

logger = logging.getLogger(__name__)
# meta developer: @PokaNikto

@loader.tds
class AutoReactMod(loader.Module):
    strings = {
        "name": "AutoReaction",
        "added": "✅ Добавлен чат {} для автореакции",
        "removed": "🚫 Удалён чат {} из автореакции",
        "no_chat": "⚠️ Не удалось найти чат с ID {}",
        "reaction_set": "✅ Установлена реакция: {}",
        "premium_set": "✅ Установлена Premium реакция по ID: {}",
        "no_reaction": "⚠️ Укажите эмодзи или его ID для реакции",
        "list_header": "<b>Список чатов с включённой автореакцией:</b>\n\n",
        "list_item": "▫️ <b>{} [ID: {}]</b> - {} {}\n",
        "premium_tag": "[Premium ID: {}]"
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            "current_reaction",
            "👍",
            "Текущая реакция (эмодзи или ID)",
            "is_premium",
            False,
            "Является ли реакция Premium эмодзи"
        )

    async def client_ready(self, client, db):
        self._db = db
        self._client = client
        self.active_chats = self.get("active_chats", {})

    def get_active_chats(self):
        return self.active_chats

    def save_active_chats(self):
        self.set("active_chats", self.active_chats)

    @loader.command(ru_doc="Добавить/удалить чат (по ID) для автореакции")
    async def auadd(self, message):
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, "<b>Укажите ID чата.</b>")
            return

        chat_id = args.strip()
        if chat_id in self.active_chats:
            del self.active_chats[chat_id]
            status = False
        else:
            try:
                chat_entity = await self._client.get_entity(int(chat_id))
                title = chat_entity.title
                self.active_chats[chat_id] = {
                    "emoji": self.config["current_reaction"],
                    "is_premium": self.config["is_premium"],
                    "title": title
                }
                status = True
            except ValueError:
                await utils.answer(message, self.strings["no_chat"].format(chat_id))
                return

        self.save_active_chats()

        response = self.strings["added"].format(title) if status else self.strings["removed"].format(chat_id)
        await utils.answer(message, response)

    @loader.command(ru_doc="Показать список чатов с включёнными автореакциями")
    async def aulist(self, message):
        if not self.active_chats:
            await utils.answer(message, "<b>Список чатов пуст.</b>")
            return

        output = self.strings["list_header"]
        for chat_id, data in self.active_chats.items():
            emoji = data.get("emoji", "?")
            is_premium = data.get("is_premium", False)
            title = data.get("title", f"Чат {chat_id}")
            premium_info = f"(ID: {emoji})" if is_premium else ""
            output += self.strings["list_item"].format(title, chat_id, emoji, premium_info)

        await utils.answer(message, output)

    @loader.command(ru_doc="Установить реакцию (обычный эмодзи или ID для Premium)")
    async def setr(self, message):
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_reaction"])
            return

        is_premium = args.isdigit()

        for chat in self.active_chats.values():
            chat["emoji"] = args
            chat["is_premium"] = is_premium

        self.config["current_reaction"] = args
        self.config["is_premium"] = is_premium

        self.save_active_chats()

        msg = self.strings["premium_set"].format(args) if is_premium else self.strings["reaction_set"].format(args)
        await utils.answer(message, msg)

    @loader.watcher()
    async def watcher(self, message):
        if not isinstance(message, types.Message):
            return

        chat_id = str(message.chat_id)

        if chat_id not in self.active_chats:
            return

        reaction_data = self.active_chats[chat_id]
        emoji = reaction_data.get("emoji")
        is_premium = reaction_data.get("is_premium", False)

        try:
            if is_premium:
                await message.react(types.ReactionCustomEmoji(document_id=int(emoji)))
            else:
                await message.react(emoji)
        except Exception as e:
            logger.error(f"Ошибка при установке реакции: {str(e)}")
