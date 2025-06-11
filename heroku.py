# meta developer: @kolyankid
# requires: python-ffmpeg

from hikkatl.tl.types import Message, MessageMediaDocument, Voice
from hikkatl.tl.custom.file import File

from .. import loader, utils
import io


@loader.tds
class VoiceManager(loader.Module):
    """Minimalist voice saver and sender"""

    strings = {"name": "VoiceManager"}

    async def vsavecmd(self, message: Message):
        """Save voice by name: .vsave [name]"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        if not reply or not reply.media or not isinstance(reply.media, MessageMediaDocument) or not reply.media.document.attributes:
            return await utils.answer(message, "❌ No voice reply")

        for attr in reply.media.document.attributes:
            if isinstance(attr, Voice):
                file: File = await reply.download_media(file=bytes)
                self.db.set("VoiceManager", args, file)
                return await utils.answer(message, f"✅ '{args}'")
        
        return await utils.answer(message, "❌ Not a voice")

    async def vvoicecmd(self, message: Message):
        """Send saved voice: .vvoice [name]"""
        args = utils.get_args_raw(message)

        data = self.db.get("VoiceManager", args, None)
        if not data:
            return await utils.answer(message, f"❌ '{args}' not found")

        file = io.BytesIO(data)
        file.name = "audio.ogg"
        await self.client.send_file(
            message.peer_id,
            file,
            voice_note=True,
            reply_to=message.reply_to_msg_id,
        )