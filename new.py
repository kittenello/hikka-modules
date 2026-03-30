
# scope heroku_min: 2.0.0

__version__ = ("1", "0", "5")

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
    """Умные автокомментарии: проверка настроек, отправка в комментарии."""
    
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
        
        "start_watch": "✅ <b>🟢 AutoComment v3.3 запущен</b>\n📺 Канал: {channel}\n🔑 Триггеры: {keywords}\n💬 Рандом: {comments}\n🔍 Проверка через: {check_delay}с\n🔔 Уведомления: {notify}\n🚫 Пропуск кнопок: {skip_btn}\n🚫 Пропуск таймеров: {skip_timer}\n📌 <b>Только новые посты!</b>",
        "stop_watch": "🛑 <b>🔴 Мониторинг остановлен</b>",
        
        "keyword_found": "🔍 <b>Триггер найден!</b>\n📝 Пост #{post_id}\n🔑 Совпадение: {matched}",
        "required_word_found": "📝 <b>Найдено требуемое слово!</b>\n💬 Пишу: «{word}»",
        "random_comment": "🎲 <b>Рандомный комментарий</b>\n💬 Пишу: «{word}»",
        
        "comment_sent": "✅ <b>Комментарий отправлен!</b>\n📝 Пост: {post_id}\n💬 Текст: «{comment}»",
        
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
        
        "check_title": "🔍 <b>Проверка настроек канала</b>\n\n",
        "check_channel": "📺 <b>Канал:</b> {title}\n├ ID: <code>{id}</code>\n├ Username: @{username}\n└ Тип: {type}\n\n",
        "check_discussion": "💬 <b>Discussion group:</b>\n├ Найдена: {found}\n├ ID: <code>{id}</code>\n└ Название: {title}\n\n",
        "check_permissions": "🔐 <b>Права доступа:</b>\n{perms}\n",
        "check_warning": "\n⚠️ <b>Внимание:</b> {warning}",
        "check_error": "❌ <b>Ошибка:</b> {error}",
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
            if hasattr(message, 'date') and message.date:
                msg_timestamp = message.date.timestamp()
                if msg_timestamp < self.watch_start_time:
                    return True
        except Exception:
            pass
        
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

    async def _find_discussion_group(self, channel):
        """Ищет discussion group для канала"""
        try:
            # Проверяем есть ли discussion в канале
            if hasattr(channel, 'discussion') and channel.discussion:
                return channel.discussion
            
            # Пробуем получить полную информацию о канале
            try:
                full_channel = await self.client(functions.channels.GetFullChannelRequest(channel))
                if full_channel and hasattr(full_channel, 'full_chat'):
                    if hasattr(full_channel.full_chat, 'linked_chat_id'):
                        linked_id = full_channel.full_chat.linked_chat_id
                        if linked_id:
                            return linked_id
            except Exception as e:
                logger.debug(f"GetFullChannel error: {e}")
            
            # Ищем среди диалогов
            async for dialog in self.client.iter_dialogs():
                if hasattr(dialog, 'is_group') and dialog.is_group:
                    try:
                        full_chat = await self.client(functions.messages.GetFullChatRequest(dialog.id))
                        if hasattr(full_chat, 'full_chat') and hasattr(full_chat.full_chat, 'linked_chat_id'):
                            if full_chat.full_chat.linked_chat_id == channel.id:
                                return dialog.id
                    except Exception:
                        continue
            
        except Exception as e:
            logger.error(f"Error finding discussion: {e}")
        
        return None

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
        
        # Проверка кулдауна
        now = datetime.now().timestamp()
        cooldown_sec = self.config["cooldown"] * 60
        if now - self.last_comment_time < cooldown_sec:
            remaining = int(cooldown_sec - (now - self.last_comment_time))
            logger.info(f"Rate limit: wait {remaining}s")
            self._save_state()
            return
        
        # Определяем текст комментария
        comment_text, is_required = self._get_comment_text(text)
        
        try:
            # 🔍 Ищем discussion group (группу для комментариев)
            comment_target = await self._find_discussion_group(post.chat)
            
            # Если не нашли discussion - ПРОПУСКАЕМ этот пост
            if not comment_target:
                logger.warning(f"⚠️ Discussion group NOT FOUND for post {post.id}. Skipping!")
                self.stats["skipped"] += 1
                self._save_state()
                # Пробуем отправить уведомление что discussion не найдена
                try:
                    await self._send_notify(
                        f"⚠️ <b>Пропущен пост!</b>\n"
                        f"📺 Канал: {getattr(post.chat, 'title', 'Unknown')}\n"
                        f"🔗 Пост: {post.id}\n"
                        f"❌ Discussion group не найдена!",
                        self.config["notify_chat"]
                    )
                except Exception:
                    pass
                return
            
            logger.info(f"✅ Found discussion: {comment_target}")
            
            # 📝 Отправляем комментарий ТОЛЬКО в discussion group
            sent_msg = await self.client.send_message(
                comment_target,
                comment_text,
                reply_to=post.id  # Это создаст комментарий к посту
            )
            
            # ✅ Сразу помечаем пост как обработанный
            self.last_comment_time = now
            self.processed_posts.add(post.id)
            self.stats["sent"] += 1
            self._save_state()
            
            logger.info(f"✅ Comment sent to discussion {comment_target}: '{comment_text}'")
            
            # 🔔 Уведомление
            channel_title = getattr(post.chat, 'title', 'Unknown')
            post_link = f"https://t.me/c/{str(post.peer_id.channel_id).replace('-100', '')}/{post.id}" if hasattr(post.peer_id, 'channel_id') else f"https://t.me/{getattr(post.chat, 'username', '')}/{post.id}"
            time_now = datetime.now().strftime("%H:%M:%S")
            
            comment_type = "📋 Требуемое" if is_required else "🎲 Рандом"
            
            notify_msg = (
                f"✅ <b>Комментарий отправлен!</b>\n"
                f"📺 {channel_title}\n"
                f"🔗 Пост: {post_link}\n"
                f"💬 Текст: «{comment_text}»\n"
                f"🏷 Тип: {comment_type}\n"
                f"⏰ {time_now}"
            )
            
            await self._send_notify(notify_msg, self.config["notify_chat"])
            
        except errors.FloodWaitError as e:
            logger.warning(f"FloodWait: wait {e.seconds}s")
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            logger.error(f"Error: {e}")
            try:
                await self._send_notify(f"❌ Ошибка: {e}", self.config["notify_chat"])
            except Exception:
                pass

    async def _send_notify(self, message: str, chat_id: str = None):
        try:
            if chat_id == "0" or not chat_id:
                target = "me"
            else:
                target = int(chat_id)
            
            await self.client.send_message(target, message, parse_mode="html", link_preview=False)
        except Exception as e:
            logger.error(f"Notify error: {e}")

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
    async def accheck(self, message: Message):
        """— Проверить настройки канала"""
        if not self.config["channel_id"]:
            return await utils.answer(message, "❌ Укажите канал: .accfg channel -1001234567890")
        
        try:
            channel_id = self.config["channel_id"]
            if isinstance(channel_id, str) and channel_id.lstrip('-').isdigit():
                channel = await self.client.get_entity(int(channel_id))
            else:
                channel = await self.client.get_entity(channel_id)
            
            text = self.strings["check_title"]
            
            # Информация о канале
            channel_type = "Канал" if hasattr(channel, 'broadcast') else "Группа"
            username = getattr(channel, 'username', 'Нет') or 'Нет'
            text += self.strings["check_channel"].format(
                title=getattr(channel, 'title', 'Unknown'),
                id=channel.id,
                username=username,
                type=channel_type
            )
            
            # Проверка discussion group
            discussion_id = await self._find_discussion_group(channel)
            if discussion_id:
                try:
                    discussion = await self.client.get_entity(discussion_id)
                    discussion_title = getattr(discussion, 'title', 'Unknown')
                    text += self.strings["check_discussion"].format(
                        found="✅ Да",
                        id=discussion_id if isinstance(discussion_id, int) else discussion_id.id,
                        title=discussion_title
                    )
                except Exception:
                    text += self.strings["check_discussion"].format(
                        found="✅ Да",
                        id=discussion_id,
                        title="Неизвестно"
                    )
            else:
                text += self.strings["check_discussion"].format(
                    found="❌ Нет",
                    id="—",
                    title="—"
                )
                text += self.strings["check_warning"].format(
                    warning="Discussion group не найдена! Комментарии будут отправляться в сам канал."
                )
            
            # Проверка прав доступа
            perms = []
            try:
                me = await self.client.get_me()
                participant = await self.client(functions.channels.GetParticipantRequest(channel, me.id))
                
                if hasattr(participant, 'participant'):
                    p = participant.participant
                    if hasattr(p, 'admin_rights') and p.admin_rights:
                        if p.admin_rights.post_messages:
                            perms.append("✅ Публикация сообщений")
                        if p.admin_rights.invite_users:
                            perms.append("✅ Приглашение пользователей")
                    elif hasattr(p, 'banned') and p.banned:
                        perms.append("❌ Забанен")
                    else:
                        perms.append("⚠️ Обычный участник")
            except Exception as e:
                perms.append(f"⚠️ Не удалось проверить: {e}")
            
            text += self.strings["check_permissions"].format(perms="\n".join(perms))
            
            await utils.answer(message, text)
            
        except Exception as e:
            await utils.answer(message, self.strings["check_error"].format(error=str(e)))

    @loader.command()
    async def accfg(self, message: Message):
        """— Показать/изменить настройки"""
        args = utils.get_args_raw(message).strip().split(maxsplit=1)
        if not args:
            text = (
                "<b>⚙️ AutoComment v3.3 настройки</b>\n\n"
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
                "<code>.actimers да/нет</code>\n"
                "<code>.accheck</code> — проверить настройки"
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
