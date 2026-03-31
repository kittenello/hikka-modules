# scope heroku_min: 2.0.0
# meta developer: @pendulation
# version: 4.0.0

import asyncio
import logging
import re
import random
from datetime import datetime
from telethon import functions, errors, types, events
from telethon.tl.types import Message
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AutoComment(loader.Module):
    """🚀 ULTRA FAST: Мгновенные автокомментарии через Events"""
    
    strings = {
        "name": "AutoComment",
        "cfg_channel_id": "ID канала или username",
        "cfg_keywords": "Ключевые слова через запятую",
        "cfg_comments": "Варианты ответов через |",
        "cfg_notify_chat": "ID для уведомлений (0 = Избранное)",
        "cfg_cooldown": "Кулдаун (минуты)",
        
        "start_watch": "🚀 <b>AutoComment v4.0 ЗАПУЩЕН</b>\n📺 Канал: <code>{channel}</code>\n⚡️ Режим: <b>Мгновенный (Events)</b>",
        "stop_watch": "🛑 <b>Остановлен</b>",
        "watching_status": "👁 <b>Статус:</b> {status}\n📊 Постов: {processed} | 💬 Комментов: {sent}",
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
        self.stats = {"processed": 0, "sent": 0}
        self.watch_start_time = None

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.is_watching = self.db.get(self.__class__.__name__, "watching", False)
        self.stats = self.db.get(self.__class__.__name__, "stats", {"processed": 0, "sent": 0})
        
        if self.is_watching and self.config["channel_id"]:
            await self._start_watch_internal()

    def _save_state(self):
        self.db.set(self.__class__.__name__, "watching", self.is_watching)
        self.db.set(self.__class__.__name__, "stats", self.stats)

    def _check_keywords(self, text: str) -> bool:
        if not text: return False
        text_lower = text.lower()
        keywords = [k.strip().lower() for k in self.config["keywords"].split(",") if k.strip()]
        return any(k in text_lower for k in keywords)

    async def _find_discussion_group(self, channel):
        """Поиск ID чата для комментариев"""
        try:
            full_channel = await self.client(functions.channels.GetFullChannelRequest(channel))
            return getattr(full_channel.full_chat, 'linked_chat_id', None)
        except:
            return None

    async def _send_notify(self, text):
        target = "me" if self.config["notify_chat"] == "0" else int(self.config["notify_chat"])
        try:
            await self.client.send_message(target, text, parse_mode="html")
        except: pass

    async def _handler(self, event):
        """Мгновенный обработчик нового сообщения"""
        if not self.is_watching: return
        
        post = event.message
        
        # 1. Проверка на дубли и старье
        if post.id in self.processed_posts or not post.text:
            return
        
        # 2. Проверка ключевых слов
        if not self._check_keywords(post.text):
            return

        # 3. Кулдаун
        now = datetime.now().timestamp()
        if now - self.last_comment_time < self.config["cooldown"] * 60:
            return

        try:
            # Ищем куда писать (дискуссия)
            discussion_id = await self._find_discussion_group(post.chat_id)
            
            if not discussion_id or discussion_id == post.chat_id:
                logger.error("❌ Чат обсуждения не найден!")
                return

            # Текст комментария
            comment_text = random.choice(self.config["comments"].split("|")).strip()

            # 🔥 САМАЯ БЫСТРАЯ ОТПРАВКА
            await self.client.send_message(
                entity=discussion_id,
                message=comment_text,
                comment_to=post.id # Ключевой параметр для Telethon
            )

            # Сохраняем состояние
            self.processed_posts.add(post.id)
            self.last_comment_time = now
            self.stats["sent"] += 1
            self._save_state()

            # Уведомление (в фоне, чтобы не тормозить)
            asyncio.create_task(self._send_notify(f"✅ <b>Взял!</b>\nКанал: {post.chat_id}\nТекст: {comment_text}"))

        except Exception as e:
            logger.error(f"Ошибка при отправке: {e}")

    async def _start_watch_internal(self):
        """Регистрация события"""
        try:
            self.client.remove_event_handler(self._handler) # Чистим старые
            
            # Определяем цель (ID или username)
            channel_input = self.config["channel_id"]
            if str(channel_input).lstrip('-').isdigit():
                target = int(channel_input)
            else:
                target = channel_input

            # Вешаем обработчик события "Новое сообщение"
            self.client.add_event_handler(self._handler, events.NewMessage(chats=target))
            self.watch_start_time = datetime.now().timestamp()
            logger.info(f"⚡️ Event Handler запущен на {target}")
        except Exception as e:
            logger.error(f"Ошибка запуска: {e}")

    @loader.command()
    async def acstart(self, message: Message):
        """Запустить мониторинг"""
        args = utils.get_args_raw(message)
        if args: self.config["channel_id"] = args
        
        if not self.config["channel_id"]:
            return await utils.answer(message, "❌ Укажите ID канала")

        self.is_watching = True
        await self._start_watch_internal()
        self._save_state()
        await utils.answer(message, self.strings["start_watch"].format(channel=self.config["channel_id"]))

    @loader.command()
    async def acstop(self, message: Message):
        """Остановить мониторинг"""
        self.is_watching = False
        self.client.remove_event_handler(self._handler)
        self._save_state()
        await utils.answer(message, self.strings["stop_watch"])

    @loader.command()
    async def acstat(self, message: Message):
        """Статистика"""
        status = "🟢 Активен" if self.is_watching else "🔴 Остановлен"
        await utils.answer(message, self.strings["watching_status"].format(
            status=status, 
            processed=self.stats.get("processed", 0), 
            sent=self.stats.get("sent", 0)
        ))
