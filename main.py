"""
Бот-тренажёр иностранных фраз для MAX.
Шаблон: по аналогии с рабочим ботом УЗИ.
"""
import subprocess
import sys
import os

def install(package):
    """Установка пакета через pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except Exception as e:
        print(f"Ошибка установки {package}: {e}")

# Пытаемся импортировать Flask, если нет - устанавливаем
try:
    from flask import Flask, request, jsonify
except ImportError:
    print("Flask не найден, устанавливаю...")
    install("flask")
    install("requests")
    from flask import Flask, request, jsonify

import json
import logging
import requests
from datetime import datetime

from bot import handle_callback, main_keyboard

# ==================== НАСТРОЙКА ====================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phrase-trainer")

app = Flask(__name__)

MAX_API = "https://platform-api.max.ru"
TOKEN = (os.environ.get("MAX_BOT_TOKEN") or "").strip()
USE_BEARER = os.environ.get("MAX_USE_BEARER", "").lower() in ("1", "true", "yes")

WEBHOOK_URL = "https://teach-english-chinese.bothost.tech/webhook"

# ==================== ФУНКЦИИ ====================

def auth_value() -> str:
    if USE_BEARER and not TOKEN.lower().startswith("bearer "):
        return f"Bearer {TOKEN}"
    return TOKEN


def api_headers():
    return {
        "Authorization": auth_value(),
        "Content-Type": "application/json",
    }


def subscribe_webhook():
    """Подписка на события MAX через webhook."""
    url = f"{MAX_API}/subscriptions"
    body = {
        "url": WEBHOOK_URL,
        "update_types": ["bot_started", "message_created", "message_callback"]
    }
    try:
        r = requests.post(url, headers=api_headers(), json=body, timeout=15)
        logger.info(f"📡 Webhook подписка: {r.status_code} {r.text[:300]}")
    except Exception as e:
        logger.error(f"Webhook ошибка: {e}")


def send_max_message(user_id, chat_id, recipient_chat_type, text, buttons=None):
    """Отправка сообщения через MAX API."""
    url = f"{MAX_API}/messages"
    params = {}

    ct = (recipient_chat_type or "").strip().lower()

    if ct in ("chat", "channel") and chat_id is not None:
        params["chat_id"] = int(chat_id)
    elif user_id is not None:
        params["user_id"] = int(user_id)
    elif chat_id is not None:
        params["chat_id"] = int(chat_id)
    else:
        logger.warning("Нет user_id и chat_id для отправки")
        return False

    payload = {"text": text}

    if buttons:
        payload["attachments"] = [{
            "type": "inline_keyboard",
            "payload": {"buttons": buttons}
        }]

    try:
        r = requests.post(url, headers=api_headers(), params=params, json=payload, timeout=15)
        if r.ok:
            logger.info(f"✅ Сообщение отправлено")
            return True
        else:
            logger.error(f"❌ Ошибка: {r.status_code} {r.text[:200]}")
            return False
    except Exception as e:
        logger.exception(f"Ошибка сети: {e}")
        return False


# ==================== ВЕБХУК ====================

@app.route("/webhook", methods=["POST", "HEAD"])
def webhook():
    if request.method == "HEAD":
        return "", 200

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        logger.warning("Тело не JSON")
        return jsonify({"ok": True}), 200

    update_type = data.get("update_type")
    logger.info(f"📥 Получен update: {update_type}")

    # Обработка нажатия "Начать"
    if update_type == "bot_started":
        chat_id = data.get("chat_id")
        user = data.get("user", {})
        user_id = user.get("user_id")

        logger.info(f"🔄 Пользователь {user_id} нажал 'Начать'")

        send_max_message(
            user_id=user_id,
            chat_id=chat_id,
            recipient_chat_type="dialog",
            text="👋 Здравствуйте!\n\n"
                 "Я бот для изучения английских и китайских фраз.\n"
                 "Выбирайте тему и учите фразы с вариантами ответов.\n\n"
                 "Выберите действие:",
            buttons=main_keyboard()
        )
        return jsonify({"ok": True}), 200

    # Обработка обычных сообщений
    if update_type == "message_created":
        msg = data.get("message", {})
        recipient = msg.get("recipient", {})
        sender = msg.get("sender", {})
        body = msg.get("body", {})

        chat_id = recipient.get("chat_id")
        chat_type = recipient.get("chat_type")
        user_id = sender.get("user_id")
        text = (body.get("text") or "").strip()

        logger.info(f"📩 Сообщение от {user_id}: '{text}'")

        if text.startswith("/start"):
            send_max_message(
                user_id=user_id,
                chat_id=chat_id,
                recipient_chat_type=chat_type,
                text="👋 Здравствуйте!\n\n"
                     "Я бот для изучения английских и китайских фраз.\n"
                     "Выбирайте тему и учите фразы с вариантами ответов.\n\n"
                     "Выберите действие:",
                buttons=main_keyboard()
            )
        else:
            send_max_message(
                user_id=user_id,
                chat_id=chat_id,
                recipient_chat_type=chat_type,
                text="Главное меню:",
                buttons=main_keyboard()
            )

        return jsonify({"ok": True}), 200

    # Обработка нажатий на кнопки
    if update_type == "message_callback":
        cb = data.get("callback", {})
        payload = cb.get("payload", "")
        callback_id = cb.get("callback_id")

        msg = cb.get("message", {})
        recipient = msg.get("recipient", {})
        sender = msg.get("sender", {})

        chat_id = recipient.get("chat_id")
        chat_type = recipient.get("chat_type")
        user_id = sender.get("user_id")

        # Вариант 2: из верхнего уровня
        if not user_id:
            user_id = data.get("user_id")
        if not chat_id:
            chat_id = data.get("chat_id")
        if not chat_type:
            chat_type = data.get("chat_type", "dialog")

        # Вариант 3: из callback.user
        if not user_id and cb.get("user"):
            user_id = cb["user"].get("user_id")

        logger.info(f"Callback: user_id={user_id}, chat_id={chat_id}, payload={payload}")

        # Отвечаем на callback (снимаем часики)
        if callback_id:
            try:
                requests.post(
                    f"{MAX_API}/answers",
                    headers=api_headers(),
                    params={"callback_id": callback_id},
                    json={"notification": "Готово"},
                    timeout=10
                )
            except Exception as e:
                logger.error(f"Ошибка answers: {e}")

        # Обрабатываем payload
        if user_id:
            text, buttons = handle_callback(user_id, payload)
            send_max_message(
                user_id=user_id,
                chat_id=chat_id,
                recipient_chat_type=chat_type,
                text=text,
                buttons=buttons
            )
        else:
            logger.error("Не удалось определить user_id")

        return jsonify({"ok": True}), 200

    return jsonify({"ok": True}), 200


# ==================== ЗДОРОВЬЕ ====================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "bot": "Phrase Trainer"}), 200


# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Задайте MAX_BOT_TOKEN")

    # Подписка на события
    subscribe_webhook()

    port = int(os.environ.get("PORT", "3000"))
    logger.info(f"🚀 Бот запущен на порту {port}")
    logger.info(f"📡 Webhook URL: {WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=port)
