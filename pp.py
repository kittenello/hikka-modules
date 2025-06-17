# meta developer: @kolyankid

from .. import loader, utils
from hikkatl.tl.patched import Message

@loader.tds
class GOVNO(loader.Module):
    """ку"""

    strings = {
        "name": "GOVNO",
    }

    async def pcmd(self, message: Message):
        """#текст"""
        args = utils.get_args_raw(message)
        
        if not args:
            return await message.delete()

        link_text = "<a href='https://t.me/samiegenius'>самые  гениальные строчки с песен. Отписаться</a>"
        full_text = f"{args}\n\n{link_text}"

        await message.edit(full_text, parse_mode="html")
