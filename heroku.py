# meta developer: @kolyankid

from .. import loader, utils
from hikkatl.tl.patched import Message

@loader.tds
class TrustedManager(loader.Module):
    """Доверенные пользователи: выполнение команд от твоего имени"""

    strings = {
        "name": "TrustedManager",
        "added": "✅ <b>{}</b> добавлен в доверенные.",
        "removed": "✅ Пользователь <code>{}</code> удалён из доверенных.",
        "not_found": "❌ Пользователь <code>{}</code> не найден в списке.",
        "no_reply": "❌ Ответь на сообщение или укажи ID и имя.",
        "list_empty": "🫥 Доверенные пользователи не найдены.",
        "list_title": "🤝 <b>Доверенные пользователи:</b>\n\n{}",
    }

    def _get_list(self):
        return self.db.get(self.strings["name"], "trusted", {})

    def _save_list(self, data: dict):
        self.db.set(self.strings["name"], "trusted", data)

    async def dovcmd(self, message: Message):
        """<id> <имя> или (reply + имя) — Добавить в доверенные"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        data = self._get_list()

        if reply:
            user = reply.sender
            if not args:
                return await utils.answer(message, self.strings("no_reply"))
            name = args.strip()
            data[user.id] = name
            self._save_list(data)
            return await utils.answer(message, self.strings("added").format(name))

        if args:
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                return await utils.answer(message, self.strings("no_reply"))
            try:
                user_id = int(parts[0])
            except ValueError:
                return await utils.answer(message, self.strings("no_reply"))
            name = parts[1]
            data[user_id] = name
            self._save_list(data)
            return await utils.answer(message, self.strings("added").format(name))

        return await utils.answer(message, self.strings("no_reply"))

    async def rdovcmd(self, message: Message):
        """<id> или reply — Удалить из доверенных"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        data = self._get_list()

        if reply:
            user = reply.sender
            if user.id in data:
                del data[user.id]
                self._save_list(data)
                return await utils.answer(message, self.strings("removed").format(user.id))
            return await utils.answer(message, self.strings("not_found").format(user.id))

        if args:
            try:
                user_id = int(args)
            except ValueError:
                return await utils.answer(message, self.strings("no_reply"))

            if user_id in data:
                del data[user_id]
                self._save_list(data)
                return await utils.answer(message, self.strings("removed").format(user_id))
            return await utils.answer(message, self.strings("not_found").format(user_id))

        return await utils.answer(message, self.strings("no_reply"))

    async def dlistcmd(self, message: Message):
        """Показать список доверенных"""
        data = self._get_list()
        if not data:
            return await utils.answer(message, self.strings("list_empty"))

        text = ""
        for uid, name in data.items():
            text += f"• <a href=\"tg://user?id={uid}\">{name}</a> [<code>{uid}</code>]\n"
        return await utils.answer(message, self.strings("list_title").format(text))

    @loader.watcher()
    async def trusted_watcher(self, message: Message):
        if not message or not message.text:
            return

        data = self._get_list()
        uid = getattr(message.from_id, "user_id", None)

        if uid not in data:
            return

        label = data[uid]
        prefix = f"{label} "

        if not message.text.startswith(prefix):
            return

        text = message.text[len(prefix):].strip()
        if not text:
            return

        if text.startswith("."):
            await self.invoke(text.split()[0], " ".join(text.split()[1:]), message=message)
        else:
            await self.client.send_message(message.peer_id, text)

