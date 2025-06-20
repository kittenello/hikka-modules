# meta developer: @kolyankid

from .. import loader, utils
from hikkatl.tl.patched import Message

@loader.tds
class NixwareSupport(loader.Module):
    """NixwareSupport"""

    strings = {
        "name": "NixwareSupport"
    }

    async def nxcmd(self, message: Message):
        """ДЕРЬМО"""
        await message.edit("write to the support on forum here -> https://nixware.cc/tickets/create")
