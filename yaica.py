# meta developer: @kolyankid

import base64
from .. import loader, utils
from hikkatl.tl.types import Message, MessageMediaDocument, DocumentAttributeAudio
import io


@loader.tds
class VoiceManager(loader.Module):
    """Сохрани и публикуй голосовое от своего имени. Команды: .vsave, .vvoice, .vdel, .vlist"""

    strings = {
        "name": "VoiceManager",
        "no_reply": "❌ Нет ответа на голосовое сообщение",
        "not_a_voice": "❌ Это не голосовое сообщение",
        "saved": "✅ Сохранено как: <code>{}</code>",
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

        is_voice = any(
            isinstance(attr, DocumentAttributeAudio) and attr.voice
            for attr in reply.media.document.attributes
        )

        if not is_voice:
            return await utils.answer(message, self.strings("not_a_voice"))

        file: bytes = await reply.download_media(file=bytes)
        encoded = base64.b64encode(file).decode("utf-8")
        self.db.set(self.VOICE_NAMESPACE, args, encoded)

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

        data = self.db.get(self.VOICE_NAMESPACE, args)
        if not data:
            return await utils.answer(message, self.strings("not_found").format(args))

        decoded = base64.b64decode(data)
        file = io.BytesIO(decoded)
        file.name = "voice.ogg"

        await self.client.send_file(
            message.peer_id,
            file,
            voice_note=True,
            reply_to=message.reply_to_msg_id,
        )

        await message.delete()

    async def vdelcmd(self, message: Message):
        """Удаляет голосовое сообщение"""
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

    async def vlistcmd(self, message: Message):
        """Список сохраненных голосовых сообщений"""
        lst = self._get_list()
        if not lst:
            return await utils.answer(message, self.strings("empty_list"))

        text = self.strings("list_header") + "\n"
        for key in sorted(lst):
            text += f"• <code>{key}</code>\n"

        return await utils.answer(message, text, parse_mode="html")
