# -*- coding: utf-8 -*-
"""Тротлер Telegram-отправки под telebot (лимиты Telegram):
- 1 сообщение/сек на приватный чат, 20/мин (~8 сек) на группу;
- 30 сообщений/сек глобально;
- tenacity: до 4 попыток с экспоненциальной задержкой при сбое отправителя.
Монотонные часы и sleep инъекционные — легко тестировать.
"""
import time
from collections import deque

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

PRIVATE_INTERVAL = 1.0
GROUP_INTERVAL = 8.0          # 20 сообщений/мин ≈ раз в 8 сек
GLOBAL_LIMIT = 30
GLOBAL_WINDOW = 1.0
RETRY_ATTEMPTS = 4


class Notifier:
    def __init__(self, clock=time.monotonic, sleep=time.sleep):
        self.clock = clock
        self.sleep = sleep
        self._last = {}          # chat_id -> время последней отправки
        self._global = deque()   # метки отправок за последнее окно

    def throttle(self, chat_id):
        """Блокирует сколько нужно и отмечает отправку. Вызывать перед send."""
        delay = self._delay_for(chat_id)
        if delay > 0:
            self.sleep(delay)
        now = self.clock()
        self._last[chat_id] = now
        while self._global and now - self._global[0] >= GLOBAL_WINDOW:
            self._global.popleft()
        self._global.append(now)

    def _delay_for(self, chat_id):
        now = self.clock()
        interval = PRIVATE_INTERVAL if chat_id >= 0 else GROUP_INTERVAL
        self._prune(now)
        dt = 0.0
        if len(self._global) >= GLOBAL_LIMIT:
            dt = max(dt, GLOBAL_WINDOW - (now - self._global[0]))
        last = self._last.get(chat_id)
        if last is not None:
            dt = max(dt, interval - (now - last))
        return max(dt, 0.0)

    def _prune(self, now):
        while self._global and now - self._global[0] >= GLOBAL_WINDOW:
            self._global.popleft()

    def call(self, sender, chat_id, text, *args, **kwargs):
        """Отправка с тротлингом + retry (экспоненциально до 8 сек)."""
        self.throttle(chat_id)
        retryer = Retrying(
            stop=stop_after_attempt(RETRY_ATTEMPTS),
            wait=wait_exponential(min=2, max=8),
            retry=retry_if_exception_type(Exception),
            sleep=self.sleep,
        )
        return retryer(sender, chat_id, text, *args, **kwargs)

    def wrap(self, sender):
        def throttled(chat_id, text, **kwargs):
            return self.call(sender, chat_id, text, **kwargs)
        return throttled
