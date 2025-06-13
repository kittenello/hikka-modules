# meta developer: @kolyankid

from .. import loader, utils
from hikkatl.tl.patched import Message

@loader.tds
class TlMod(loader.Module):
    """Конвертирует текст в анонимый шрифт"""

    strings = {"name": "TlMod"}

    STYLE_MAP = {
        'а': 'ᴀ', 'б': 'б', 'в': 'ʙ', 'г': 'ᴦ', 'д': 'д', 'е': 'ᴇ',
        'ё': 'ё', 'ж': 'ж', 'з': 'з', 'и': 'и', 'й': 'й', 'к': 'ᴋ',
        'л': 'ᴧ', 'м': 'ʍ', 'н': 'н', 'о': 'о', 'п': 'ᴨ', 'р': 'ᴩ',
        'с': 'ᴄ', 'т': 'ᴛ', 'у': 'у', 'ф': 'ɸ', 'х': 'х', 'ц': 'ц',
        'ч': 'ч', 'ш': 'ɯ', 'щ': 'щ', 'ъ': 'ъ', 'ы': 'ы', 'ь': 'ь',
        'э': '϶', 'ю': 'ю', 'я': 'я',

        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ',
        'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ',
        'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ',
        's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
        'y': 'ʏ', 'z': 'ᴢ'
    }

    async def tlcmd(self, message: Message):
        """.tl [text] ААА"""
        args = utils.get_args_raw(message)
        if not args:
            return await message.delete()

        converted = ''.join(self.STYLE_MAP.get(c.lower(), c) for c in args)
        await message.edit(converted)