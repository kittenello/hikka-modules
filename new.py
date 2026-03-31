
# scope heroku_min: 2.0.0

__version__ = ("1", "0", "6")

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

# Отключаем лишние логи
logging.getLogger('telethon').setLevel(logging.WARNING)

@loader.tds
class AutoComment(loader.Module):
    """Умные автокомментарии: ТОЛЬКО комментарии, БЕЗ дублей!"""
    
    strings = {
        "name": "AutoComment",
        "cfg_channel_id": "ID канала для мониторинга",
        "cfg_keywords": "Ключевые слова для триггера",
        "cfg_comments": "Рандомные комментарии через |",
        "cfg_notify_chat": "ID чата для уведомлений (0 = Избранное)",
        "cfg_check_delay": "Задержка (сек)",
        "cfg_cooldown": "Кулдаун (мин)",
        "cfg_skip_buttons": "Пропускать кнопки? (да/нет)",
        "cfg_skip_timers": "Пропускать таймеры? (да/нет)",
        
        "start_watch": "✅ <b>🟢 AutoComment v3.5 ЗАПУЩЕН</b>\n📺 Канал: {channel}\n🔑 Триггеры: {keywords}\n💬 Рандом: {comments}\n🔔 Уведомления: {notify}\n📌 <b>Только новые посты! Только комментарии!</b>",
        "stop_watch": "🛑 <b>🔴 Остановлен</b>",
        
        "skip_button": "⏭ Пропущено: кнопки",
        "skip_timer": "⏭ Пропущено: таймер",
        "skip_old_post": "⏭ Пропущено: старый пост",
        "skip_no_discussion": "⏭ Пропущено: нет discussion",
        
        "rate_limit": "⏳ Кулдаун: {seconds}с",
        "no_config": "❌ Настрой: .accfg",
        "watching_status": "👁 <b>Статус:</b> {status}\n📺 {channel}\n📊 Постов: {processed} | 💬 Комментов: {sent} | ⏭ Пропущено: {skipped}",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("channel_id", "", lambda: self.strings["cfg_channel_id"]),
            loader.ConfigValue("keywords", "первые,коммент,подарок,ракета,мишка,раздача,дроп,напиш,комментируйте,комы,получат,100,111,101,50,20,30", lambda: self.strings["cfg_keywords"]),
            loader.ConfigValue("comments", "изи|я|забрал|тут|моё|го|взял|комы где|приветик", lambda: self.strings["cfg_comments"]),
            loader.ConfigValue("notify_chat", "0", lambda: self.strings["cfg_notify_chat"]),
            loader.ConfigValue("check_delay", "0", lambda: self.strings["cfg_check_delay"], 
                              validator=loader.validators.Integer(minimum=0, maximum=30)),
            loader.ConfigValue("cooldown", "1", lambda: self.strings["cfg_cooldown"], 
                              validator=loader.validators.Integer(minimum=0, maximum=60)),
            loader.ConfigValue("skip_buttons", "да", lambda: "Пропускать кнопки?", 
                              validator=loader.validators.Choice(["да", "нет"])),
            loader.ConfigValue("skip_timers", "да", lambda: "Пропускать таймеры?", 
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
        if hasattr(message, 'reply_markup') and message.reply_markup:
            return True
        return False

    def _has_timer_text(self, text: str) -> bool:
        if not text:
            return False
        text_lower = text.lower()
        timer_patterns = [
            r'итоги\s+(через|в)',
            r'результаты\s+(через|в)',
            r'подведение\s+итогов',
            r'выложу\s+(в\s+комах|в\s+комментариях)',
            r'нажать\s+на\s+кнопк',
            r'кликни\s+на\s+кнопк',
            r'жми\s+кнопк',
            r'кнопка\s+ниже',
        ]
        for pattern in timer_patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    def _extract_required_word(self, text: str) -> str:
        if not text:
            return None
        patterns = [
            r'напиш[еиу][тс]?[\s:]+["\']([^"\']+)["\']',
            r'напиш[еиу][тс]?[\s:]+([а-яa-z]{3,})',
            r'коммент\s+["\']([^"\']+)["\']',
            r'сообщение\s+["\']([^"\']+)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                word = match.group(1).strip()
                if 2 <= len(word) <= 30:
                    return word
        return None

    def _should_skip_post(self, message: Message, text: str) -> tuple[bool, str]:
        if self.config["skip_buttons"] == "да" and self._has_buttons(message):
            return True, "button"
        if self.config["skip_timers"] == "да" and self._has_timer_text(text):
            return True, "timer"
        return False, ""

    def _is_old_post(self, message: Message) -> bool:
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
        required_word = self._extract_required_word(post_text)
        if required_word:
            logger.info(f"Required word: {required_word}")
            return required_word, True
        comments = self._parse_comments()
        random_comment = random.choice(comments)
        logger.info(f"Random comment: {random_comment}")
        return random_comment, False

    async def _find_discussion_group(self, channel):
        """Ищет discussion group — ИСПРАВЛЕНО"""
        logger.info(f"🔍 Ищем discussion для канала {channel.id}")
        
        try:
            # 1. Проверяем channel.discussion
            if hasattr(channel, 'discussion') and channel.discussion:
                logger.info(f"✅ Найдено через channel.discussion: {channel.discussion}")
                return channel.discussion
            
            # 2. GetFullChannel
            try:
                full_channel = await self.client(functions.channels.GetFullChannelRequest(channel))
                if full_channel and hasattr(full_channel, 'full_chat'):
                    if hasattr(full_channel.full_chat, 'linked_chat_id'):
                        linked_id = full_channel.full_chat.linked_chat_id
                        if linked_id and linked_id != channel.id:
                            logger.info(f"✅ Найдено через linked_chat_id: {linked_id}")
                            return linked_id
            except Exception as e:
                logger.debug(f"GetFullChannel error: {e}")
            
            # 3. Ищем среди диалогов
            logger.info("🔍 Ищем в диалогах...")
            async for dialog in self.client.iter_dialogs():
                if hasattr(dialog, 'is_group') and dialog.is_group:
                    try:
                        full_chat = await self.client(functions.messages.GetFullChatRequest(dialog.id))
                        if hasattr(full_chat, 'full_chat') and hasattr(full_chat.full_chat, 'linked_chat_id'):
                            if full_chat.full_chat.linked_chat_id == channel.id:
                                logger.info(f"✅ Найдено в диалогах: {dialog.id}")
                                return dialog.id
                    except:
                        continue
            
        except Exception as e:
            logger.error(f"Error finding discussion: {e}")
        
        logger.warning(f"❌ Discussion НЕ найдена для канала {channel.id}")
        return None

    async def _send_notify(self, message: str, chat_id: str = None):
        """ИСПРАВЛЕНО: отправка уведомлений"""
        try:
            if chat_id == "0" or not chat_id:
                # Saved Messages - используем 'me'
                target = "me"
            else:
                target = int(chat_id)
            
            await self.client.send_message(target, message, parse_mode="html", link_preview=False)
            logger.debug(f"Notify sent to {target}")
        except Exception as e:
            logger.error(f"Notify error: {e}")

    async def _process_post(self, post: Message):
        """ИСПРАВЛЕНО: ТОЛЬКО комментарии через ветку обсуждения"""
        
        # 1. Защита от дублей
        if post.id in self.processed_posts:
            logger.debug(f"⏭ Post {post.id} уже в кэше")
            return
        
        # 2. Базовые проверки (старый пост, сервисное, пустое)
        if self._is_old_post(post) or isinstance(post, types.MessageService) or not post.text:
            return
        
        self.stats["processed"] += 1
        text = post.text
        
        # 3. Поиск триггеров
        matched = self._check_keywords(text)
        if not matched:
            self._save_state()
            return
        
        # 4. Проверка на кнопки/таймеры
        should_skip, skip_reason = self._should_skip_post(post, text)
        if should_skip:
            logger.info(f"⏭ Пропуск поста {post.id}: {skip_reason}")
            self.stats["skipped"] += 1
            self._save_state()
            return
            
        # 5. Кулдаун
        now = datetime.now().timestamp()
        if now - self.last_comment_time < self.config["cooldown"] * 60:
            return

        # 6. Подготовка текста
        comment_text, is_required = self._get_comment_text(text)
        
        try:
            # Ищем ID чата для обсуждений
            discussion_id = await self._find_discussion_group(post.chat)
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: Если discussion_id совпадает с каналом — это ошибка
            if not discussion_id or discussion_id == post.chat_id:
                logger.error(f"❌ Для канала {post.chat_id} не привязан чат обсуждения!")
                self.stats["skipped"] += 1
                return

            # 🔥 ОТПРАВКА: Используем comment_to для железной привязки к ветке
            await self.client.send_message(
                entity=discussion_id,
                message=comment_text,
                comment_to=post  # Telethon сам найдет правильный reply_to внутри чата
            )
            
            logger.info(f"✅ Коммент отправлен в обсуждение {discussion_id} к посту {post.id}")
            
            # Обновляем состояние СРАЗУ после успешной отправки
            self.last_comment_time = now
            self.processed_posts.add(post.id)
            self.stats["sent"] += 1
            self._save_state()
            
            # Уведомление в логи/избранное
            channel_title = getattr(post.chat, 'title', 'Channel')
            time_now = datetime.now().strftime("%H:%M:%S")
            notify_msg = (
                f"✅ <b>Комментарий оставлен!</b>\n"
                f"📺 {channel_title}\n"
                f"💬 «{comment_text}»\n"
                f"⏰ {time_now}"
            )
            await self._send_notify(notify_msg, self.config["notify_chat"])
            
        except errors.FloodWaitError as e:
            logger.warning(f"FloodWait: {e.seconds}s")
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            logger.error(f"❌ Ошибка в _process_post: {e}")

    async def _watch_loop(self):
        """Цикл мониторинга канала"""
        channel_id = self.config["channel_id"]
        if not channel_id:
            return
        
        try:
            # Приводим ID к числу, если это строка из цифр
            target = int(channel_id) if str(channel_id).lstrip('-').isdigit() else channel_id
            channel = await self.client.get_entity(target)
        except Exception as e:
            logger.error(f"Не удалось получить доступ к каналу {channel_id}: {e}")
            return
        
        logger.info(f"🟢 Мониторинг запущен: {getattr(channel, 'title', channel_id)}")
        
        while self.is_watching:
            try:
                # Берем последние 5 сообщений, чтобы не пропустить быстрые посты
                async for post in self.client.iter_messages(channel, limit=5):
                    await self._process_post(post)
                
                # Задержка между проверками (оптимально 5-10 сек)
                await asyncio.sleep(7)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(15)

    def _start_watch_internal(self):
        self.watch_start_time = datetime.now().timestamp()
        self.watch_start_post_id = None
        self._save_state()
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
        self._watch_task = asyncio.create_task(self._watch_loop())

    @loader.command()
    async def acstart(self, message: Message):
        """[channel_id] — Запустить"""
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
            notify="Избранное" if self.config["notify_chat"]=="0" else self.config["notify_chat"],
        ))

    @loader.command()
    async def acstop(self, message: Message):
        """— Остановить"""
        self.is_watching = False
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
        self._save_state()
        await utils.answer(message, self.strings["stop_watch"])

    @loader.command()
    async def accheck(self, message: Message):
        """— Проверка канала"""
        if not self.config["channel_id"]:
            return await utils.answer(message, "❌ .accfg channel -100...")
        try:
            channel_id = self.config["channel_id"]
            if isinstance(channel_id, str) and channel_id.lstrip('-').isdigit():
                channel = await self.client.get_entity(int(channel_id))
            else:
                channel = await self.client.get_entity(channel_id)
            
            text = f"🔍 <b>Проверка</b>\n\n"
            text += f"📺 <b>Канал:</b> {getattr(channel, 'title', 'Unknown')}\n"
            text += f"├ ID: <code>{channel.id}</code>\n"
            text += f"└ Username: @{getattr(channel, 'username', 'Нет') or 'Нет'}\n\n"
            
            discussion_id = await self._find_discussion_group(channel)
            if discussion_id:
                try:
                    discussion = await self.client.get_entity(discussion_id)
                    text += f"💬 <b>Discussion:</b>\n"
                    text += f"├ Найдена: ✅\n"
                    text += f"├ ID: <code>{discussion_id if isinstance(discussion_id, int) else discussion_id.id}</code>\n"
                    text += f"└ Название: {getattr(discussion, 'title', 'Unknown')}\n"
                except:
                    text += f"💬 <b>Discussion:</b> найдена (ID: {discussion_id})\n"
            else:
                text += f"💬 <b>Discussion:</b> ❌ НЕ НАЙДЕНА!\n"
                text += f"⚠️ <i>Создайте в настройках канала</i>\n"
            
            await utils.answer(message, text)
        except Exception as e:
            await utils.answer(message, f"❌ Ошибка: {e}")

    @loader.command()
    async def accfg(self, message: Message):
        """— Настройки"""
        args = utils.get_args_raw(message).strip().split(maxsplit=1)
        if not args:
            text = (
                f"<b>⚙️ AutoComment v3.5</b>\n\n"
                f"📺 <b>Канал:</b> <code>{self.config['channel_id']}</code>\n"
                f"🔑 <b>Триггеры:</b> <code>{self.config['keywords']}</code>\n"
                f"💬 <b>Рандом:</b> <code>{self.config['comments']}</code>\n"
                f"🔔 <b>Уведомления:</b> <code>{self.config['notify_chat']}</code>\n"
                f"🔄 <b>Кулдаун:</b> <code>{self.config['cooldown']}мин</code>\n\n"
                f"<b>💡 Команды:</b>\n"
                f"<code>.ackey word1,word2</code>\n"
                f"<code>.accomm я|изи</code>\n"
                f"<code>.acnotify 0</code>\n"
                f"<code>.accheck</code>"
            )
            return await utils.answer(message, text)
        key, value = args[0], args[1] if len(args) > 1 else ""
        keys_map = {
            "channel": "channel_id", "keys": "keywords", "keywords": "keywords",
            "comm": "comments", "comments": "comments",
            "notify": "notify_chat", "cooldown": "cooldown",
        }
        config_key = keys_map.get(key.lower())
        if not config_key:
            return await utils.answer(message, f"❌ Неизвестно: {key}")
        if config_key == "cooldown":
            try:
                val = int(value)
                self.config[config_key] = max(0, min(60, val))
            except:
                return await utils.answer(message, "❌ Число")
        else:
            self.config[config_key] = value
        self._save_state()
        await utils.answer(message, f"✅ <b>{config_key}</b> = <code>{value}</code>")

    @loader.command()
    async def ackey(self, message: Message):
        """<word1,word2> — Триггеры"""
        keywords = utils.get_args_raw(message).strip()
        if not keywords:
            return await utils.answer(message, "❌ .ackey первые,коммент")
        self.config["keywords"] = keywords
        self._save_state()
        await utils.answer(message, f"✅ <b>Триггеры:</b> <code>{keywords}</code>")

    @loader.command()
    async def accomm(self, message: Message):
        """<comm1|comm2> — Комментарии"""
        comments = utils.get_args_raw(message).strip()
        if not comments:
            return await utils.answer(message, "❌ .accomm изи|я")
        self.config["comments"] = comments
        self._save_state()
        await utils.answer(message, f"✅ <b>Рандом:</b> <code>{comments}</code>")

    @loader.command()
    async def acnotify(self, message: Message):
        """<chat_id> — Уведомления (0 = Избранное)"""
        chat_id = utils.get_args_raw(message).strip()
        if not chat_id:
            return await utils.answer(message, "❌ .acnotify 0")
        self.config["notify_chat"] = chat_id
        self._save_state()
        target = "Избранное" if chat_id == "0" else chat_id
        await utils.answer(message, f"🔔 <b>Уведомления:</b> <code>{target}</code>")

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
            text += f"\n🎯 <b>Успешно:</b> {self.stats['sent']}"
        if self.watch_start_time:
            start_dt = datetime.fromtimestamp(self.watch_start_time)
            text += f"\n📌 <b>Запущен:</b> {start_dt.strftime('%H:%M:%S')}"
        await utils.answer(message, text)

    @loader.command()
    async def acclear(self, message: Message):
        """— Очистить кэш"""
        self.processed_posts.clear()
        self.watch_start_time = None
        self.watch_start_post_id = None
        self._save_state()
        await utils.answer(message, "🗑 <b>Кэш очищен</b>")
