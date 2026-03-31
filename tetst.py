# scope heroku_min: 2.0.0
# meta developer: @pendulation
# version: 4.1.0 (Strict One-Shot Edition)

import asyncio
import logging
import re
import random
import time
from datetime import datetime
from telethon import functions, errors, types, events
from telethon.tl.types import Message
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AutoComment(loader.Module):
    """🚀 ULTRA FAST: Пишет ОДИН раз и только на НОВЫЕ посты"""
    
    strings = {
        "name": "AutoComment",
        "cfg_channel_id": "ID канала или username",
        "cfg_keywords": "Ключевые слова через запятую",
        "cfg_comments": "Варианты ответов через |",
        "cfg_notify_chat": "ID для уведомлений (0 = Избранное)",
        "cfg_cooldown": "Кулдаун (минуты)",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("channel_id", "", lambda: self.strings["cfg_channel_id"]),
            loader.ConfigValue("keywords", "ракета,подарок,получат,коммент,первых,раздача,дроп", lambda: self.strings["cfg_keywords"]),
            loader.ConfigValue("comments", "я|тут|взял|изи|моё|го", lambda: self.strings["cfg_comments"]),
            loader.ConfigValue("notify_chat", "0", lambda: self.strings["cfg_notify_chat"]),
            loader.ConfigValue("cooldown", "1", lambda: self.strings["cfg_cooldown"], 
                              validator=loader.validators.Integer(minimum=0, maximum=60)),
        )
        self.is_watching = False
        self.last_comment_time = 0
        self.processed_posts = set()
        self.start_ts = 0  # Время запуска скрипта

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.is_watching = self.db.get(self.__class__.__name__, "watching", False)
        
        if self.is_watching and self.config["channel_id"]:
            await self._start_watch_internal()

    def _check_keywords(self, text: str) -> bool:
        if not text: return False
        text_lower = text.lower()
        keywords = [k.strip().lower() for k in self.config["keywords"].split(",") if k.strip()]
        return any(k in text_lower for k in keywords)

    async def _find_discussion_group(self, channel_id):
        try:
            full = await self.client(functions.channels.GetFullChannelRequest(channel_id))
            return getattr(full.full_chat, 'linked_chat_id', None)
        except: return None

    async def _handler(self, event):
        if not self.is_watching or not event.is_channel: return
        
        post = event.message

        # ✅ ЖЕСТКАЯ ПРОВЕРКА 1: Только посты, вышедшие ПОСЛЕ запуска
        # (Защита от комментирования старых постов при старте)
        if post.date.timestamp() < self.start_ts:
            return

        # ✅ ЖЕСТКАЯ ПРОВЕРКА 2: Один пост - один комментарий
        if post.id in self.processed_posts:
            return

        # ✅ ЖЕСТКАЯ ПРОВЕРКА 3: Ключевые слова
        if not self._check_keywords(post.text):
            return

        # ✅ ЖЕСТКАЯ ПРОВЕРКА 4: Кулдаун
        now = time.time()
        if now - self.last_comment_time < self.config["cooldown"] * 60:
            return

        # Если все проверки прошли, помечаем пост СРАЗУ (до отправки), чтобы не было дублей
        self.processed_posts.add(post.id)

        try:
            discussion_id = await self._find_discussion_group(post.chat_id)
            if not discussion_id: return

            comment_text = random.choice(self.config["comments"].split("|")).strip()

            # 🔥 ОТПРАВКА
            await self.client.send_message(
                entity=discussion_id,
                message=comment_text,
                comment_to=post.id
            )

            self.last_comment_time = now
            logger.info(f"✅ Коммент отправлен к посту {post.id}")
            
            # Уведомление
            target = "me" if self.config["notify_chat"] == "0" else int(self.config["notify_chat"])
            asyncio.create_task(self.client.send_message(target, f"🚀 <b>Взял!</b>\nТекст: {comment_text}"))

        except Exception as e:
            logger.error(f"Ошибка: {e}")

    async def _start_watch_internal(self):
        try:
            self.start_ts = time.time() # Фиксируем время старта
            self.processed_posts.clear() # Очищаем кэш при новом запуске
            
            self.client.remove_event_handler(self._handler)
            
            channel_input = self.config["channel_id"]
            target = int(channel_input) if str(channel_input).lstrip('-').isdigit() else channel_input

            self.client.add_event_handler(self._handler, events.NewMessage(chats=target))
            logger.info(f"⚡️ Мониторинг {target} запущен. Игнорируем всё что было до {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            logger.error(f"Ошибка запуска: {e}")

    @loader.command()
    async def acstart(self, message: Message):
        """Запустить (игнорирует старые посты)"""
        args = utils.get_args_raw(message)
        if args: self.config["channel_id"] = args
        
        if not self.config["channel_id"]:
            return await utils.answer(message, "❌ Укажите ID")

        self.is_watching = True
        await self._start_watch_internal()
        self.db.set(self.__class__.__name__, "watching", True)
        await utils.answer(message, f"🚀 <b>AutoComment ЗАПУЩЕН</b>\n📺 Канал: <code>{self.config['channel_id']}</code>\n<i>Старые посты будут проигнорированы.</i>")

    @loader.command()
    async def acstop(self, message: Message):
        """Остановить"""
        self.is_watching = False
        self.client.remove_event_handler(self._handler)
        self.db.set(self.__class__.__name__, "watching", False)
        await utils.answer(message, "🛑 <b>Остановлен</b>")
