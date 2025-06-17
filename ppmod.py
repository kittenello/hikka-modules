# meta developer: @kolyankid

from .. import loader, utils
from hikkatl.tl.patched import Message

@loader.tds
class PPMod(loader.Module):
    """che takoe"""

    strings = {
        "name": "PPMod",
    }

    async def ppcmd(self, message: Message):
        """<текст> — Добавляет текст и подписку"""
        args = utils.get_args_raw(message)
        
        if not args:
            return await message.delete()

        link_text = "[самые гениальные строчки с песен. Отписаться](https://t.me/samiegenius)" 
        full_text = f"{args}\n\n{link_text}"
        
        await message.edit(full_text)