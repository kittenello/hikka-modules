# meta developer: @tootsintoots
# meta banner: https://github.com/sqlmerr/hikka_mods/blob/main/assets/banners/voicemanager.png?raw=true

import base64
from .. import loader, utils
from hikkatl.tl.types import Message, MessageMediaDocument, DocumentAttributeAudio
import io


@loader.tds
class VoiceManager(loader.Module):
    """Save and reuse voice messages by name"""

    strings = {"name": "VoiceManager"}

    async def vsavecmd(self, message: Message):
        """Save voice by name: .vsave [name]"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        if not reply or not reply.media or not isinstance(reply.media, MessageMediaDocument):
            return await utils.answer(message, "❌ No voice reply")

        is_voice = any(
            isinstance(attr, DocumentAttributeAudio) and attr.voice
            for attr in reply.media.document.attributes
        )

        if not is_voice:
            return await utils.answer(message, "❌ Not a voice")

        file: bytes = await reply.download_media(file=bytes)

        # Кодируем в base64 для сохранения в БД 
        encoded = base64.b64encode(file).decode("utf-8")
        self.db.set("VoiceManager", args, encoded)

        return await utils.answer(message, f"✅ '{args}'")

    async def vvoicecmd(self, message: Message):
        """Send saved voice: .vvoice [name]"""
        args = utils.get_args_raw(message)

        data = self.db.get("VoiceManager", args)
        if not data:
            return await utils.answer(message, f"❌ '{args}' not found")

        # Декодируем обратно в байты
        decoded = base64.b64decode(data)
        file = io.BytesIO(decoded)
        file.name = "audio.ogg"

        await self.client.send_file(
            message.peer_id,
            file,
            voice_note=True,
            reply_to=message.reply_to_msg_id,
        )