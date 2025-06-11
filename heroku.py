# meta developer: @sqlmerr_m
# meta icon: https://github.com/sqlmerr/hikka_mods/blob/main/assets/icons/qrcode.png?raw=true
# meta banner: https://github.com/sqlmerr/hikka_mods/blob/main/assets/banners/qrcode.png?raw=true 
# requires: qrcode pillow

import io
import logging
from typing import Union

import qrcode
from PIL import Image, ImageDraw

from hikkatl.tl.types import Message as HikkaMessage
from hikkatl.tl.patched import Message

from .. import loader, utils
from ..inline.types import InlineMessage


@loader.tds
class QRCode(loader.Module):
    """Module for generating QR codes from text or links"""

    strings = {
        "name": "QRCode",
        "no_args": "<emoji document_id=5210952531676504517>❌</emoji> <b>No arguments provided!</b>",
        "generated_qr": "<emoji document_id=5370896721267232777>✅</emoji> <b>QR code generated:</b>",
        "qr_button": "🔁 Regenerate",
    }

    strings_ru = {
        "no_args": "<emoji document_id=5210952531676504517>❌</emoji> <b>Не указаны аргументы!</b>",
        "generated_qr": "<emoji document_id=5370896721267232777>✅</emoji> <b>QR-код сгенерирован:</b>",
        "qr_button": "🔁 Пересоздать",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "default_size",
                300,
                lambda: "Default size of QR code image in pixels",
                validator=loader.validators.Integer(minimum=100),
            ),
            loader.ConfigValue(
                "default_color",
                "black",
                lambda: "Default color of QR code",
            ),
            loader.ConfigValue(
                "default_background",
                "white",
                lambda: "Default background color of QR code",
            ),
        )

    @loader.command(ru_doc="[ссылка] - Генерирует QR-код")
    async def qr(self, message: HikkaMessage):
        """[text_or_link] - Generates QR code"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings("no_args"))
            return

        # Generate QR code
        qr_img = await self._generate_qr(
            data=args,
            size=self.config["default_size"],
            color=self.config["default_color"],
            background=self.config["default_background"],
        )

        # Convert to BytesIO
        bio = io.BytesIO()
        qr_img.save(bio, format="PNG")
        bio.seek(0)

        # Send inline form with button
        await self.inline.form(
            message=message,
            text=self.strings("generated_qr"),
            reply_markup=[
                [
                    {
                        "text": self.strings("qr_button"),
                        "callback": self._regenerate_qr,
                        "args": (args,),
                    }
                ]
            ],
            photo=bio,
        )

    async def _regenerate_qr(self, call: InlineMessage, data: str):
        qr_img = await self._generate_qr(
            data=data,
            size=self.config["default_size"],
            color=self.config["default_color"],
            background=self.config["default_background"],
        )

        bio = io.BytesIO()
        qr_img.save(bio, format="PNG")
        bio.seek(0)

        await call.edit(
            text=self.strings("generated_qr"),
            reply_markup=[
                [
                    {
                        "text": self.strings("qr_button"),
                        "callback": self._regenerate_qr,
                        "args": (data,),
                    }
                ]
            ],
            photo=bio,
        )

    async def _generate_qr(self, data: str, size: int, color: str, background: str) -> Image:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color=color, back_color=background).convert("RGBA")

        # Resize image to desired size
        return img.resize((size, size), Image.LANCZOS)