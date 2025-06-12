# meta developer: @kolyankid

import base64
from .. import loader, utils
from hikkatl.tl.types import Message, MessageMediaDocument, DocumentAttributeAudio
import io


@loader.tds
class VoiceManager(loader.Module):
    """Сохрани и публикуй голосовое от своего имени, удобно, быстро, четко. Использование: .vvoice/vsave/vdel [name]."""

    strings = {
        "name": "VoiceManager",
        "no_reply": "❌ No voice reply",
        "not_a_voice": "❌ Not a voice message",
        "saved": "✅ Saved as: <code>{}</code>",
        "not_found": "❌ Not found: <code>{}</code>",
        "usage_vsave": "❌ Usage: .vsave [name]",
        "usage_vvoice": "❌ Usage: .vvoice [name]",
        "deleted": "✅ Deleted: <code>{}</code>",
        "empty_list": "❌ No saved voices",
        "list_header": "📃 Saved voices:",
    }

    strings_ru = {
        "name": "VoiceManager",
        "no_reply": "❌ Нет ответа на голосовое сообщение",
        "not_a_voice": "❌ Это не голосовое сообщение",
        "saved": "✅ Сохранено как: <code>{}</code>",
        "not_found": "❌ Не найдено: <code>{}</code>",
        "usage_vsave": "❌ Использование: .vsave [name]",
        "usage_vvoice": "❌ Использование: .vvoice [name]",
        "deleted": "✅ Удалено: <code>{}</code>",
        "empty_list": "❌ Нет сохранённых голосовых",
        "list_header": "📃 Сохранённые голосовые:",
    }

    async def vsavecmd(self, message: Message):
        """Save voice"""
        args = utils.get_args_raw(message)
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
        self.db.set("VoiceManager", args, encoded)

        return await utils.answer(message, self.strings("saved").format(args))

    async def vvoicecmd(self, message: Message):
        """Send saved voice"""
        args = utils.get_args_raw(message)

        data = self.db.get("VoiceManager", args)
        if not data:
            return await utils.answer(message, self.strings("not_found").format(args))

        decoded = base64.b64decode(data)
        file = io.BytesIO(decoded)
        file.name = "audio.ogg"

        sent = await self.client.send_file(
            message.peer_id,
            file,
            voice_note=True,
            reply_to=message.reply_to_msg_id,
        )

        await message.delete()

    async def vdelcmd(self, message: Message):
        """Delete saved voice"""
        args = utils.get_args_raw(message)

        if not self.db.get("VoiceManager", args):
            return await utils.answer(message, self.strings("not_found").format(args))

        self.db.remove("VoiceManager", args)
        return await utils.answer(message, self.strings("deleted").format(args))

    async def vlistcmd(self, message: Message):
        """List all saved voices"""
        try:
            data = self.db.get("VoiceManager")
        except KeyError:
            return await utils.answer(message, self.strings("empty_list"))

        if not data:
            return await utils.answer(message, self.strings("empty_list"))

        text = self.strings("list_header") + "\n"
        for key in sorted(data.keys()):
            text += f"• <code>{key}</code>\n"

        return await utils.answer(message, text, parse_mode="html")
