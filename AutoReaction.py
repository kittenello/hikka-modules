# meta developer: @your_username
# 1

import asyncio
import uuid
from telethon.tl.types import Message, ReactionEmoji
from telethon.tl.functions.messages import SendReactionRequest
from telethon.errors import ChannelInvalidError, ChannelPrivateError, ChatAdminRequiredError
from .. import loader, utils


@loader.tds
class AutoReactionsMod(loader.Module):
    """Automatically adds reactions to messages in specified chats from your account"""

    strings = {
        "name": "AutoReactions",
        "added": "<b>✅ Auto-reaction added with ID: <code>{}</code>\nChat: <a href='{}'>{}</a>\nReaction: {}</b>",
        "list": "<b>📋 Auto-reactions list:</b>\n{}",
        "no_reactions": "<b>📭 No auto-reactions set</b>",
        "deleted": "<b>🗑 Auto-reaction with ID: <code>{}</code> deleted</b>",
        "invalid_args": "<b>❌ Invalid arguments. Use: <code>.au [@chat/ID] [reaction/ID]</code> or reply to a message with a reaction</b>",
        "invalid_reaction": "<b>❌ Invalid reaction. Reply to a message with a reaction or provide a valid emoji/ID</b>",
        "chat_not_found": "<b>❌ Chat not found or inaccessible. Ensure the chat exists and you have access to it</b>",
        "_cmd_doc_au": "[@chat/ID] [reaction/ID] - Set auto-reaction for a chat",
        "_cmd_doc_aulist": "Show list of active auto-reactions",
        "_cmd_doc_aud": "[ID] - Delete auto-reaction by ID",
    }

    strings_ru = {
        "added": "<b>✅ Автореакция добавлена с ID: <code>{}</code>\nЧат: <a href='{}'>{}</a>\nРеакция: {}</b>",
        "list": "<b>📋 Список автореакций:</b>\n{}",
        "no_reactions": "<b>📭 Нет установленных автореакций</b>",
        "deleted": "<b>🗑 Автореакция с ID: <code>{}</code> удалена</b>",
        "invalid_args": "<b>❌ Неверные аргументы. Используйте: <code>.au [@чат/ID] [реакция/ID]</code> или ответьте на сообщение с реакцией</b>",
        "invalid_reaction": "<b>❌ Неверная реакция. Ответьте на сообщение с реакцией или укажите действительный эмодзи/ID</b>",
        "chat_not_found": "<b>❌ Чат не найден или недоступен. Убедитесь, что чат существует и у вас есть к нему доступ</b>",
        "_cmd_doc_au": "[@чат/ID] [реакция/ID] - Установить автореакцию для чата",
        "_cmd_doc_aulist": "Показать список активных автореакций",
        "_cmd_doc_aud": "[ID] - Удалить автореакцию по ID",
    }

    def __init__(self):
        self.config = loader.ModuleConfig()
        self._reactions = {}  # {id: {"chat_id": int, "reaction": str}}

    async def client_ready(self):
        self._log_chat, _ = await utils.asset_channel(
            self._client,
            "heroku-autoreaction",
            "📋 Chat for auto-reaction logs",
            silent=True,
            invite_bot=True,
            _folder="hikka",
        )
        self._log_chat_id = f"-100{self._log_chat.id}"

    async def aucmd(self, message: Message):
        """[@chat/ID] [reaction/ID] - Set auto-reaction for a chat"""
        args = utils.get_args_raw(message).split(maxsplit=1)

        if len(args) < 2 and not message.is_reply:
            await utils.answer(message, self.strings("invalid_args"))
            return

        chat_id = args[0] if len(args) >= 1 else None
        try:
            chat = await self._client.get_entity(chat_id) if chat_id else message.chat
            chat_id = utils.get_chat_id(chat)
            chat_title = getattr(chat, "title", "Private Chat")
            chat_link = f"https://t.me/{chat.username}" if getattr(chat, "username",
                                                                   None) else f"https://t.me/c/{chat_id}"
        except (ChannelInvalidError, ChannelPrivateError, ValueError):
            await utils.answer(message, self.strings("chat_not_found"))
            return
        except Exception:
            await utils.answer(message, self.strings("invalid_args"))
            return

        reaction = None
        if message.is_reply:
            replied = await message.get_reply_message()
            if replied.reactions:
                reaction = replied.reactions.reactions[0].reaction
            else:
                await utils.answer(message, self.strings("invalid_reaction"))
                return
        else:
            reaction = args[1]

        if not isinstance(reaction, (str, ReactionEmoji)):
            await utils.answer(message, self.strings("invalid_reaction"))
            return

        reaction_id = str(uuid.uuid4())
        self._reactions[reaction_id] = {
            "chat_id": chat_id,
            "reaction": reaction.emoticon if isinstance(reaction, ReactionEmoji) else reaction
        }

        self.set("reactions", self._reactions)

        reaction_str = reaction.emoticon if isinstance(reaction, ReactionEmoji) else reaction
        await utils.answer(
            message,
            self.strings("added").format(reaction_id, chat_link, utils.escape_html(chat_title), reaction_str)
        )

        await self.inline.bot.send_message(
            self._log_chat_id,
            self.strings("added").format(reaction_id, chat_link, utils.escape_html(chat_title), reaction_str),
            parse_mode="HTML",
        )

    async def aulistcmd(self, message: Message):
        """Show list of active auto-reactions"""
        if not self._reactions:
            await utils.answer(message, self.strings("no_reactions"))
            return

        response = []
        for rid, data in self._reactions.items():
            try:
                chat = await self._client.get_entity(data["chat_id"])
                chat_title = getattr(chat, "title", "Private Chat")
                chat_link = f"https://t.me/{chat.username}" if getattr(chat, "username",
                                                                       None) else f"https://t.me/c/{data['chat_id']}"
                response.append(
                    f"🆔 <code>{rid}</code>\n"
                    f"💬 <a href='{chat_link}'>{utils.escape_html(chat_title)}</a>\n"
                    f"😊 {data['reaction']}\n"
                )
            except Exception:
                response.append(
                    f"🆔 <code>{rid}</code>\n"
                    f"💬 Unknown chat (ID: {data['chat_id']})\n"
                    f"😊 {data['reaction']}\n"
                )

        await utils.answer(message, self.strings("list").format("\n".join(response)), parse_mode="HTML")

    async def audcmd(self, message: Message):
        """[ID] - Delete auto-reaction by ID"""
        args = utils.get_args_raw(message)
        if not args or args not in self._reactions:
            await utils.answer(message, self.strings("invalid_args"))
            return

        del self._reactions[args]
        self.set("reactions", self._reactions)

        await utils.answer(message, self.strings("deleted").format(args))

        await self.inline.bot.send_message(
            self._log_chat_id,
            self.strings("deleted").format(args),
            parse_mode="HTML",
        )

    async def watcher(self, message: Message):
        """Watch for messages in chats with auto-reactions"""
        if not self._reactions:
            return

        chat_id = utils.get_chat_id(message)
        for data in self._reactions.values():
            if data["chat_id"] == chat_id:
                try:
                    await self.allclients[0](SendReactionRequest(
                        peer=message.chat_id,
                        msg_id=message.id,
                        reaction=[ReactionEmoji(emoticon=data["reaction"])]
                    ))
                except ChatAdminRequiredError:
                    pass
