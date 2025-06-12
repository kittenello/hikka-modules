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

    VOICE_NAMESPACE = "VoiceManager"
    VOICE_LIST_KEY = "_list"

    def _get_list(self):
        return self.db.get(self.VOICE_NAMESPACE, self.VOICE_LIST_KEY) or []

    def _save_list(self, lst):
        self.db.set(self.VOICE_NAMESPACE, self.VOICE_LIST_KEY, lst)

    async def vsavecmd(self, message: Message):
        """Save voice: .vsave [name] (reply to voice)"""
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
        """Send saved voice: .vvoice [name]"""
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
        """Delete saved voice: .vdel [name]"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, self.strings("not_found").format(args))

        if not self.db.get(self.VOICE_NAMESPACE, args):
            return await utils.answer(message, self.strings("not_found").format(args))

        self.db.remove(self.VOICE_NAMESPACE, args)

        lst = self._get_list()
        if args in lst:
            lst.remove(args)
            self._save_list(lst)

        return await utils.answer(message, self.strings("deleted").format(args))

    async def vlistcmd(self, message: Message):
        """List all saved voices: .vlist"""
        lst = self._get_list()
        if not lst:
            return await utils.answer(message, self.strings("empty_list"))

        text = self.strings("list_header") + "\n"
        for key in sorted(lst):
            text += f"• <code>{key}</code>\n"

        return await utils.answer(message, text, parse_mode="html")
