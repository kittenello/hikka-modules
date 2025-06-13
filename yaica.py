# meta developer: @kolyankid

import base64
import io
from .. import loader, utils
from hikkatl.tl.types import Message, MessageMediaDocument, DocumentAttributeAudio


@loader.tds
class VoiceManager(loader.Module):
    """Сохраняй голосовые сообщения/кружки и воспроизводи их от себя как голосовое сообщение. Быстро, удобно, четко, легко. Команды: .vsave, .vvoice, .vdel, .vlist"""

    strings = {
        "name": "VoiceManager",
        "no_reply": "❌ Нет ответа на голосовое или кружок",
        "not_voice": "❌ Это не голосовое сообщение или кружок",
        "saved": "✅ Сохранено как: 🎙 <code>{}</code>",
        "not_found": "❌ Не найдено: <code>{}</code>",
        "usage_vsave": "❌ Использование: .vsave [название]",
        "usage_vvoice": "❌ Использование: .vvoice [название]",
        "deleted": "✅ Удалено: <code>{}</code>",
        "empty_list": "❌ Нет сохранённых голосовых",
        "list_header": "📃 Сохранённые голосовые:",
    }

    VOICE_NAMESPACE = "VoiceManager"
    VOICE_LIST_KEY = "_list"

    def _get_list(self):
        return self.db.get(self.VOICE_NAMESPACE, self.VOICE_LIST_KEY) or []

    def _save_list(self, lst):
        self.db.set(self.VOICE_NAMESPACE, self.VOICE_LIST_KEY, lst)

    async def vsavecmd(self, message: Message):
        """Сохраняет голосовое сообщение"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, self.strings("usage_vsave"))

        reply = await message.get_reply_message()
        if not reply or not reply.media or not isinstance(reply.media, MessageMediaDocument):
            return await utils.answer(message, self.strings("no_reply"))

        attrs = reply.media.document.attributes
        is_voice = any(isinstance(attr, DocumentAttributeAudio) and attr.voice for attr in attrs)
        is_round = reply.media.document.supports_streaming and reply.media.document.mime_type == "video/mp4"

        if not is_voice and not is_round:
            return await utils.answer(message, self.strings("not_voice"))

        file: bytes = await reply.download_media(file=bytes)
        encoded = base64.b64encode(file).decode("utf-8")
        self.db.set(self.VOICE_NAMESPACE, args, {"data": encoded})

        lst = self._get_list()
        if args not in lst:
            lst.append(args)
            self._save_list(lst)

        return await utils.answer(message, self.strings("saved").format(args))

    async def vvoicecmd(self, message: Message):
        """Отправляет сохранённое голосовое сообщение"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, self.strings("usage_vvoice"))

        obj = self.db.get(self.VOICE_NAMESPACE, args)
        if not obj or "data" not in obj:
            return await utils.answer(message, self.strings("not_found").format(args))

        try:
            decoded = base64.b64decode(obj["data"])
        except Exception:
            return await utils.answer(message, self.strings("not_found").format(args))

        file = io.BytesIO(decoded)
        file.name = "voice.ogg"

        await self.client.send_file(
            message.peer_id,
            file,
            voice_note=True,
            reply_to=message.reply_to_msg_id
        )

        await message.delete()

    async def vdelcmd(self, message: Message):
        """Удаляет сохранённое голосовое сообщение"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, self.strings("not_found").format(args))

        if not self.db.get(self.VOICE_NAMESPACE, args):
            return await utils.answer(message, self.strings("not_found").format(args))

        self.db.set(self.VOICE_NAMESPACE, args, None)

        lst = self._get_list()
        if args in lst:
            lst.remove(args)
            self._save_list(lst)

        return await utils.answer(message, self.strings("deleted").format(args))

    def _render_voice_page(self, page: int, per_page: int = 10):
        lst = self._get_list()
        pages = max(1, (len(lst) + per_page - 1) // per_page)
        page = max(1, min(page, pages))

        start = (page - 1) * per_page
        end = start + per_page
        current = lst[start:end]

        text = self.strings("list_header") + "\n"
        for key in current:
            text += f"🎙 <code>{key}</code>\n"

        buttons = []
        if pages > 1:
            buttons.append([
                {
                    "text": "⬅️" if page > 1 else "⛔",
                    "callback": self._page_callback,
                    "args": [str(page - 1)],
                },
                {
                    "text": f"{page}/{pages}",
                    "callback": self._noop,
                },
                {
                    "text": "➡️" if page < pages else "⛔",
                    "callback": self._page_callback,
                    "args": [str(page + 1)],
                },
            ])

        return text, buttons

    async def vlistcmd(self, message: Message):
        """Список сохранённых голосов"""
        lst = self._get_list()
        if not lst:
            return await utils.answer(message, self.strings("empty_list"))

        text, markup = self._render_voice_page(1)
        await self.inline.form(
            text=text,
            message=message,
            reply_markup=markup
        )

    async def _page_callback(self, call):
        page = int(call.args[0]) if call.args and call.args[0].isdigit() else 1
        text, markup = self._render_voice_page(page)
        await call.edit(text, reply_markup=markup)

    async def _noop(self, call):
        await call.answer("Вы уже на этой странице ✅")
