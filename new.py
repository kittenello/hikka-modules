
# scope heroku_min: 2.0.0

__version__ = ("1", "0", "4")

# meta developer: @pendulation

import asyncio
import logging
import re
import random
from datetime import datetime
from telethon import functions, errors, types
from telethon.tl.types import Message, Channel, PeerChannel
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AutoComment(loader.Module):
    """Умные автокомментарии: только новые посты после запуска."""
    
    strings = {
        "name": "AutoComment",
        "cfg_channel_id": "ID канала для мониторинга (например: -1001234567890)",
        "cfg_keywords": "Ключевые слова для триггера (через запятую)",
        "cfg_comments": "Рандомные комментарии через | (если не найдено требуемое слово)",
        "cfg_notify_chat": "ID чата для уведомлений (0 = Избранное)",
        "cfg_check_delay": "Задержка ПЕРЕД проверкой позиции (сек)",
        "cfg_cooldown": "Кулдаун между комментариями (мин)",
        "cfg_skip_buttons": "Пропускать посты с кнопками? (да/нет)",
        "cfg_skip_timers": "Пропускать посты с таймером итогов? (да/нет)",
        
        "start_watch": "✅ <b>🟢 AutoComment v3.2 запущен</b>\n📺 Канал: {channel}\n🔑 Триггеры: {keywords}\n💬 Рандом: {comments}\n🔍 Проверка через: {check_delay}с\n🔔 Уведомления: {notify}\n🚫 Пропуск кнопок: {skip_btn}\n🚫 Пропуск таймеров: {skip_timer}\n📌 <b>Только новые посты!</b>",
        "stop_watch": "🛑 <b>🔴 Мониторинг остановлен</b>",
        
        "keyword_found": "🔍 <b>Триггер найден!</b>\n📝 Пост #{post_id}\n🔑 Совпадение: {matched}",
        "required_word_found": "📝 <b>Найдено требуемое слово!</b>\n💬 Пишу: «{word}»",
        "random_comment": "🎲 <b>Рандомный комментарий</b>\n💬 Пишу: «{word}»",
        
        "comment_sent": "✅ <b>Комментарий отправлен!</b>\n📝 Пост: {post_id}\n💬 Текст: «{comment}»\n⏳ Проверяю позицию...",
        
        "notify_first": "🥇 <b>ТЫ ПЕРВЫЙ!</b>\n📺 {channel}\n🔗 Пост: {post_link}\n💬 Твой коммент: «{comment}»\n⏰ {time}",
        "notify_not_first": "📍 <b>Не первый</b>\n📺 {channel}\n🔗 Пост: {post_link}\n💬 Твой коммент: «{comment}»\n📊 Позиция: #{position}\n⏰ {time}",
        
        "skip_button": "⏭ <b>Пропущено:</b> пост с кнопками",
        "skip_timer": "⏭ <b>Пропущено:</b> пост с таймером итогов",
        "skip_old_post": "⏭ <b>Пропущено:</b> старый пост (до запуска)",
        "skip_no_comments": "⏭ <b>Пропущено:</b> комментарии закрыты",
        
        "error_send": "❌ Ошибка отправки: {error}",
        "error_check": "❌ Ошибка проверки позиции: {error}",
        "rate_limit": "⏳ Кулдаун: ждём {seconds}с",
        "no_config": "❌ Настрой модуль: .accfg",
        "watching_status": "👁 <b>Статус:</b> {status}\n📺 Канал: {channel}\n📊 Постов: {processed} | 💬 Комментов: {sent} | ⏭ Пропущено: {skipped}",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("channel_id", "", lambda: self.strings["cfg_channel_id"]),
            loader.ConfigValue("keywords", "первые,коммент,подарок,ракета,мишка,раздача,дроп,напиш,комментируйте,комы,получат,100,111,101,50,20,30", lambda: self.strings["cfg_keywords"]),
            loader.ConfigValue("comments", "изи|я|забрал|тут|моё|го|взял|комы где", lambda: self.strings["cfg_comments"]),
            loader.ConfigValue("notify_chat", "0", lambda: self.strings["cfg_notify_chat"]),
            loader.ConfigValue("check_delay", "2", lambda: self.strings["cfg_check_delay"], 
                              validator=loader.validators.Integer(minimum=0, maximum=30)),
            loader.ConfigValue("cooldown", "1", lambda: self.strings["cfg_cooldown"], 
                              validator=loader.validators.Integer(minimum=0, maximum=60)),
            loader.ConfigValue("skip_buttons", "да", lambda: "Пропускать посты с кнопками?", 
                              validator=loader.validators.Choice(["да", "нет"])),
            loader.ConfigValue("skip_timers", "да", lambda: "Пропускать посты с таймером итогов?", 
                              validator=loader.validators.Choice(["да", "нет"])),
        )
        self.is_watching = False
        self.last_comment_time = 0
        self.processed_posts = set()
        self.stats = {"processed": 0, "sent": 0, "skipped": 0}
        self._watch_task = None
        self.watch_start_time = None
        self.watch_start_post_id = None

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.is_watching = self.db.get(self.__class__.__name__, "watching", False)
        self.processed_posts = set(self.db.get(self.__class__.__name__, "processed", []))
        self.stats = self.db.get(self.__class__.__name__, "stats", {"processed": 0, "sent": 0, "skipped": 0})
        self.watch_start_time = self.db.get(self.__class__.__name__, "watch_start_time", None)
        self.watch_start_post_id = self.db.get(self.__class__.__name__, "watch_start_post_id", None)
        if self.is_watching and self.config["channel_id"]:
            self._start_watch_internal()

    def _save_state(self):
        self.db.set(self.__class__.__name__, "watching", self.is_watching)
        self.db.set(self.__class__.__name__, "processed", list(self.processed_posts)[-1000:])
        self.db.set(self.__class__.__name__, "stats", self.stats)
        self.db.set(self.__class__.__name__, "watch_start_time", self.watch_start_time)
        self.db.set(self.__class__.__name__, "watch_start_post_id", self.watch_start_post_id)

    def _parse_keywords(self):
        raw = self.config["keywords"].strip()
        return [k.strip().lower() for k in raw.split(",") if k.strip()] if raw else []

    def _parse_comments(self):
        raw = self.config["comments"].strip()
        return [c.strip() for c in raw.split("|") if c.strip()] if raw else ["изи"]

    def _check_keywords(self, text: str) -> list:
        """Улучшенная проверка на триггеры с учетом вариаций"""
        if not text:
            return []
        text_lower = text.lower()
        
        config_keywords = self._parse_keywords()
        
        giveaway_patterns = [
            r'\d+\s*первых\s*(коммент|комментариев|комов)',
            r'первые\s+\d+\s*(коммент|комментариев|комов)',
            r'получат\s+по\s+\w+',
            r'\d+\s*первых\s+получат',
            r'комментируйте\s+ниже',
            r'комы\s+где',
            r'сообщения\s+бесплатн',
            r'подарок\s+коммент',
            r'оставляйте\s+коммент',
        ]
        
        matched = []
        
        for keyword in config_keywords:
            if keyword in text_lower:
                matched.append(keyword)
        
        for pattern in giveaway_patterns:
            if re.search(pattern, text_lower):
                match = re.search(pattern, text_lower)
                matched.append(f"pattern:{match.group(0)}")
        
        return matched

    def _has_buttons(self, message: Message) -> bool:
        """Проверяет, есть ли под постом кнопки (inline keyboard)"""
        if hasattr(message, 'reply_markup') and message.reply_markup:
            return True
        return False

    def _has_timer_text(self, text: str) -> bool:
        """Проверяет текст на наличие таймеров/итогов"""
        if not text:
            return False
        text_lower = text.lower()
        timer_patterns = [
            r'итоги\s+(через|в|через\s*\d+|в\s*\d+)',
            r'результаты\s+(через|в)',
            r'подведение\s+итогов',
            r'выложу\s+(в\s+комах|в\s+комментариях|через)',
            r'нажать\s+на\s+кнопк',
            r'кликни\s+на\s+кнопк',
            r'жми\s+кнопк',
            r'кнопка\s+ниже',
            r'участвовать\s+через\s+кнопк',
        ]
        for pattern in timer_patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    def _extract_required_word(self, text: str) -> str:
        """Извлекает требуемое слово для комментария из текста поста."""
        if not text:
            return None
        
        patterns = [
            r'напиш[еиу][тс]?[\s:]+["\']([^"\']+)["\']',
            r'напиш[еиу][тс]?[\s:]+([а-яa-z]{3,})',
            r'коммент\s+["\']([^"\']+)["\']',
            r'сообщение\s+["\']([^"\']+)["\']',
            r'слово\s+["\']([^"\']+)["\']',
            r'текст\s+["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                word = match.group(1).strip()
                if 2 <= len(word) <= 30:
                    return word
        
        return None

    def _should_skip_post(self, message: Message, text: str) -> tuple[bool, str]:
        """Проверяет, нужно ли пропустить пост."""
        if self.config["skip_buttons"] == "да" and self._has_buttons(message):
            return True, "button"
        
        if self.config["skip_timers"] == "да" and self._has_timer_text(text):
            return True, "timer"
        
        return False, ""

    def _is_old_post(self, message: Message) -> bool:
        """Проверяет, был ли пост создан до запуска мониторинга"""
        if not self.watch_start_time:
            return False
        
        try:
            # Сравниваем дату сообщения с временем запуска
            if hasattr(message, 'date') and message.date:
                msg_timestamp = message.date.timestamp()
                if msg_timestamp < self.watch_start_time:
                    return True
        except Exception:
            pass
        
        # Также проверяем по ID поста (если известно)
        if self.watch_start_post_id and message.id < self.watch_start_post_id:
            return True
        
        return False

    def _get_comment_text(self, post_text: str) -> tuple[str, bool]:
        """Определяет, какой комментарий отправить."""
        required_word = self._extract_required_word(post_text)
        if required_word:
            logger.info(f"Required word found: {required_word}")
            return required_word, True
        
        comments = self._parse_comments()
        random_comment = random.choice(comments)
        logger.info(f"Random comment: {random_comment}")
        return random_comment, False

    async def _get_my_comment_position(self, post: Message, my_message_id: int, comment_target=None) -> tuple[bool, int]:
        """Проверяет позицию нашего комментария"""
        try:
            target = comment_target if comment_target else post.peer_id
            
            comments = []
            async for comment in self.client.iter_messages(
                target, 
                reply_to=post.id, 
                limit=50
            ):
                comments.append(comment)
            
            if not comments:
                return True, 1
            
            comments.sort(key=lambda x: x.date)
            
            for i, comment in enumerate(comments, 1):
                if comment.id == my_message_id:
                    return i == 1, i
            
            return False, 0
            
        except Exception as e:
            logger.debug(f"Position check error: {e}")
            return False, 0

    async def _send_notify(self, message: str, chat_id: str = None):
        try:
            target = int(chat_id) if chat_id and chat_id != "0" else await self.client.get_me()
            await self.client.send_message(target, message, parse_mode="html", link_preview=False)
        except Exception as e:
            logger.error(f"Notify error: {e}")

    async def _process_post(self, post: Message):
        """Основная логика обработки поста"""
        if post.id in self.processed_posts:
            return
        
        # 🔴 ПРОВЕРКА: только новые посты после запуска
        if self._is_old_post(post):
            self.stats["skipped"] += 1
            self._save_state()
            logger.debug(f"Skip old post {post.id} (before watch start)")
            return
        
        if isinstance(post, types.MessageService) or not post.text:
            return
        
        self.stats["processed"] += 1
        text = post.text or ""
        
        matched = self._check_keywords(text)
        if not matched:
            self._save_state()
            return
        
        should_skip, skip_reason = self._should_skip_post(post, text)
        if should_skip:
            self.stats["skipped"] += 1
            self._save_state()
            if skip_reason == "button":
                logger.info(f"Skip post {post.id}: buttons detected")
            elif skip_reason == "timer":
                logger.info(f"Skip post {post.id}: timer detected")
            return
        
        now = datetime.now().timestamp()
        cooldown_sec = self.config["cooldown"] * 60
        if now - self.last_comment_time < cooldown_sec:
            remaining = int(cooldown_sec - (now - self.last_comment_time))
            logger.info(f"Rate limit: wait {remaining}s")
            self._save_state()
            return
        
        comment_text, is_required = self._get_comment_text(text)
        
        try:
            comment_target = post.peer_id
            
            try:
                if hasattr(post, 'chat') and post.chat:
                    channel = await self.client.get_entity(post.chat_id)
                    if hasattr(channel, 'discussion'):
                        discussion = channel.discussion
                        if discussion:
                            comment_target = discussion
                            logger.info(f"Found discussion group: {discussion.id}")
            except Exception as e:
                logger.debug(f"Error getting discussion: {e}")
            
            sent_msg = await self.client.send_message(
                comment_target,
                comment_text,
                reply_to=post.id
            )
            
            self.last_comment_time = now
            self.processed_posts.add(post.id)
            self.stats["sent"] += 1
            self._save_state()
            
            logger.info(f"Comment sent to {comment_target}: '{comment_text}' (required: {is_required})")
            
            check_delay = self.config["check_delay"]
            if check_delay > 0:
                await asyncio.sleep(check_delay)
            
            is_first, position = await self._get_my_comment_position(post, sent_msg.id, comment_target)
            
            channel_title = getattr(post.chat, 'title', 'Unknown')
            post_link = f"https://t.me/c/{str(post.peer_id.channel_id).replace('-100', '')}/{post.id}" if hasattr(post.peer_id, 'channel_id') else f"https://t.me/{getattr(post.chat, 'username', '')}/{post.id}"
            time_now = datetime.now().strftime("%H:%M:%S")
            
            comment_type = "📋 Требуемое" if is_required else "🎲 Рандом"
            
            if is_first:
                notify_msg = (
                    f"🥇 <b>ТЫ ПЕРВЫЙ!</b>\n"
                    f"📺 {channel_title}\n"
                    f"🔗 Пост: {post_link}\n"
                    f"💬 Твой коммент: «{comment_text}»\n"
                    f"🏷 Тип: {comment_type}\n"
                    f"⏰ {time_now}"
                )
                logger.info(f"🥇 FIRST! Post {post.id}")
            else:
                notify_msg = (
                    f"📍 <b>Не первый</b>\n"
                    f"📺 {channel_title}\n"
                    f"🔗 Пост: {post_link}\n"
                    f"💬 Твой коммент: «{comment_text}»\n"
                    f"🏷 Тип: {comment_type}\n"
                    f"📊 Позиция: #{position if position > 0 else '?'}\n"
                    f"⏰ {time_now}"
                )
                logger.info(f"📍 Not first (#{position}). Post {post.id}")
            
            await self._send_notify(notify_msg, self.config["notify_chat"])
            
        except errors.FloodWaitError as e:
            logger.warning(f"FloodWait: wait {e.seconds}s")
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            logger.error(f"Error: {e}")
            await self._send_notify(f"❌ Ошибка: {e}", self.config["notify_chat"])

    async def _watch_loop(self):
        channel_id = self.config["channel_id"]
        if not channel_id:
            logger.error("Channel ID not configured")
            return
        
        try:
            if isinstance(channel_id, str) and channel_id.lstrip('-').isdigit():
                channel = await self.client.get_entity(int(channel_id))
            else:
                channel = await self.client.get_entity(channel_id)
        except Exception as e:
            logger.error(f"Can't get channel: {e}")
            return
        
        logger.info(f"Start watching: {channel}")
        
        while self.is_watching:
            try:
                async for post in self.client.iter_messages(channel, limit=5):
                    await self._process_post(post)
                
                await asyncio.sleep(8)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watch error: {e}")
                await asyncio.sleep(20)
        
        logger.info("Watch loop stopped")

    def _start_watch_internal(self):
        # 📌 Запоминаем время запуска и ID последнего поста
        self.watch_start_time = datetime.now().timestamp()
        self.watch_start_post_id = None
        self._save_state()
        
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
        self._watch_task = asyncio.create_task(self._watch_loop())

    @loader.command()
    async def acstart(self, message: Message):
        """[channel_id] — Запустить мониторинг"""
        args = utils.get_args_raw(message).strip()
        if args and isinstance(args, str) and args.lstrip('-').isdigit():
            self.config["channel_id"] = args
        
        if not self.config["channel_id"]:
            return await utils.answer(message, self.strings["no_config"])
        
        self.is_watching = True
        self._start_watch_internal()
        self._save_state()
        
        await utils.answer(message, self.strings["start_watch"].format(
            channel=self.config["channel_id"],
            keywords=self.config["keywords"],
            comments=self.config["comments"],
            check_delay=self.config["check_delay"],
            notify="Избранное" if self.config["notify_chat"]=="0" else self.config["notify_chat"],
            skip_btn="✅" if self.config["skip_buttons"]=="да" else "❌",
            skip_timer="✅" if self.config["skip_timers"]=="да" else "❌"
        ))

    @loader.command()
    async def acstop(self, message: Message):
        """— Остановить мониторинг"""
        self.is_watching = False
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
        self._save_state()
        await utils.answer(message, self.strings["stop_watch"])

    @loader.command()
    async def accfg(self, message: Message):
        """— Показать/изменить настройки"""
        args = utils.get_args_raw(message).strip().split(maxsplit=1)
        if not args:
            text = (
                "<b>⚙️ AutoComment v3.2 настройки</b>\n\n"
                f"📺 <b>Канал:</b> <code>{self.config['channel_id']}</code>\n"
                f"🔑 <b>Триггеры:</b> <code>{self.config['keywords']}</code>\n"
                f"💬 <b>Рандом:</b> <code>{self.config['comments']}</code>\n"
                f"⏱ <b>Проверка:</b> <code>{self.config['check_delay']}с</code>\n"
                f"🔔 <b>Уведомления:</b> <code>{self.config['notify_chat']}</code>\n"
                f"🔄 <b>Кулдаун:</b> <code>{self.config['cooldown']}мин</code>\n"
                f"🚫 <b>Пропуск кнопок:</b> <code>{self.config['skip_buttons']}</code>\n"
                f"🚫 <b>Пропуск таймеров:</b> <code>{self.config['skip_timers']}</code>\n\n"
                "<b>💡 Команды:</b>\n"
                "<code>.ackey word1,word2</code>\n"
                "<code>.accomm я|изи</code>\n"
                "<code>.acdelay 3</code>\n"
                "<code>.acnotify 0</code>\n"
                "<code>.acbuttons да/нет</code>\n"
                "<code>.actimers да/нет</code>"
            )
            return await utils.answer(message, text)
        
        key, value = args[0], args[1] if len(args) > 1 else ""
        keys_map = {
            "channel": "channel_id", "keys": "keywords", "keywords": "keywords",
            "comm": "comments", "comments": "comments", "delay": "check_delay",
            "notify": "notify_chat", "cooldown": "cooldown",
            "buttons": "skip_buttons", "timers": "skip_timers",
        }
        config_key = keys_map.get(key.lower())
        if not config_key:
            return await utils.answer(message, f"❌ Неизвестно: {key}")
        if config_key in ["check_delay", "cooldown"]:
            try:
                val = int(value)
                if config_key == "check_delay" and not (0 <= val <= 30):
                    return await utils.answer(message, "❌ Delay: 0-30с")
                if config_key == "cooldown" and not (0 <= val <= 60):
                    return await utils.answer(message, "❌ Cooldown: 0-60мин")
                self.config[config_key] = val
            except ValueError:
                return await utils.answer(message, "❌ Число нужно")
        elif config_key in ["skip_buttons", "skip_timers"]:
            if value.lower() not in ["да", "нет", "yes", "no"]:
                return await utils.answer(message, "❌ Используйте: да/нет")
            self.config[config_key] = "да" if value.lower() in ["да", "yes"] else "нет"
        else:
            self.config[config_key] = value
        self._save_state()
        await utils.answer(message, f"✅ <b>{config_key}</b> = <code>{value}</code>")

    @loader.command()
    async def ackey(self, message: Message):
        """<word1,word2> — Ключевые слова-триггеры"""
        keywords = utils.get_args_raw(message).strip()
        if not keywords:
            return await utils.answer(message, "❌ .ackey первые,коммент,подарок")
        self.config["keywords"] = keywords
        self._save_state()
        await utils.answer(message, f"✅ <b>Триггеры:</b> <code>{keywords}</code>")

    @loader.command()
    async def accomm(self, message: Message):
        """<comm1|comm2> — Рандомные комментарии"""
        comments = utils.get_args_raw(message).strip()
        if not comments:
            return await utils.answer(message, "❌ .accomm изи|я|забрал")
        self.config["comments"] = comments
        self._save_state()
        await utils.answer(message, f"✅ <b>Рандом:</b> <code>{comments}</code>")

    @loader.command()
    async def acdelay(self, message: Message):
        """<сек> — Задержка перед проверкой позиции"""
        arg = utils.get_args_raw(message).strip()
        if not arg or not arg.isdigit():
            return await utils.answer(message, "❌ .acdelay 2 (0-30 сек)")
        val = int(arg)
        if not (0 <= val <= 30):
            return await utils.answer(message, "❌ 0-30 секунд")
        self.config["check_delay"] = val
        self._save_state()
        await utils.answer(message, f"⏱ <b>Проверка через:</b> <code>{val}с</code>")

    @loader.command()
    async def acnotify(self, message: Message):
        """<chat_id> — Чат для уведомлений (0 = Избранное)"""
        chat_id = utils.get_args_raw(message).strip()
        if not chat_id:
            return await utils.answer(message, "❌ .acnotify 0")
        self.config["notify_chat"] = chat_id
        self._save_state()
        target = "Избранное" if chat_id == "0" else chat_id
        await utils.answer(message, f"🔔 <b>Уведомления:</b> <code>{target}</code>")

    @loader.command()
    async def acbuttons(self, message: Message):
        """<да/нет> — Пропускать посты с кнопками"""
        arg = utils.get_args_raw(message).strip().lower()
        if arg not in ["да", "нет", "yes", "no"]:
            return await utils.answer(message, "❌ .acbuttons да/нет")
        self.config["skip_buttons"] = "да" if arg in ["да", "yes"] else "нет"
        self._save_state()
        status = "✅ Вкл" if self.config["skip_buttons"] == "да" else "❌ Выкл"
        await utils.answer(message, f"🚫 <b>Пропуск кнопок:</b> {status}")

    @loader.command()
    async def actimers(self, message: Message):
        """<да/нет> — Пропускать посты с таймером итогов"""
        arg = utils.get_args_raw(message).strip().lower()
        if arg not in ["да", "нет", "yes", "no"]:
            return await utils.answer(message, "❌ .actimers да/нет")
        self.config["skip_timers"] = "да" if arg in ["да", "yes"] else "нет"
        self._save_state()
        status = "✅ Вкл" if self.config["skip_timers"] == "да" else "❌ Выкл"
        await utils.answer(message, f"🚫 <b>Пропуск таймеров:</b> {status}")

    @loader.command()
    async def acstat(self, message: Message):
        """— Статистика"""
        status = "🟢 Активен" if self.is_watching else "🔴 Остановлен"
        channel = self.config["channel_id"] or "не задан"
        text = self.strings["watching_status"].format(
            status=status, channel=channel,
            processed=self.stats["processed"], 
            sent=self.stats["sent"],
            skipped=self.stats["skipped"]
        )
        if self.stats["sent"] > 0:
            text += f"\n🎯 <b>Успешно:</b> {self.stats['sent']} комментов"
        if self.watch_start_time:
            start_dt = datetime.fromtimestamp(self.watch_start_time)
            text += f"\n📌 <b>Запущен:</b> {start_dt.strftime('%H:%M:%S')}"
        await utils.answer(message, text)

    @loader.command()
    async def acclear(self, message: Message):
        """— Очистить кэш постов"""
        self.processed_posts.clear()
        self.watch_start_time = None
        self.watch_start_post_id = None
        self._save_state()
        await utils.answer(message, "🗑 <b>Кэш очищен</b>")
