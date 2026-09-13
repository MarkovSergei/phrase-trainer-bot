import os
import logging
import requests
from flask import Flask, request, jsonify

from bot import handle_callback, main_keyboard, user_state


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phrase-trainer")

app = Flask(__name__)

MAX_API = "https://platform-api.max.ru"
TOKEN = (os.environ.get("MAX_BOT_TOKEN") or "").strip()


def api_headers():
    return {
        "Authorization": TOKEN,
        "Content-Type": "application/json",
    }


def send_message(user_id, chat_id, chat_type, text, buttons=None):
    """Отправка сообщения в MAX."""
    url = f"{MAX_API}/messages"
    params = {}

    ct = (chat_type or "").strip().lower()

    if ct in ("chat", "channel") and chat_id is not None:
        params["chat_id"] = int(chat_id)
    elif user_id is not None:
        params["user_id"] = int(user_id)
    elif chat_id is not None:
        params["chat_id"] = int(chat_id)
    else:
        logger.warning("Нет user_id и chat_id")
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
            return True
        logger.error(f"Ошибка отправки: {r.status_code} {r.text[:200]}")
        return False
    except Exception as e:
        logger.exception(f"Ошибка сети: {e}")
        return False


@app.route("/webhook", methods=["POST", "HEAD"])
def webhook():
    if request.method == "HEAD":
        return "", 200

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": True}), 200

    update_type = data.get("update_type")
    logger.info(f"📥 Update: {update_type}")

    # --- Старт бота ---
    if update_type == "bot_started":
        chat_id = data.get("chat_id")
        user = data.get("user", {})
        user_id = user.get("user_id")

        send_message(
            user_id=user_id,
            chat_id=chat_id,
            chat_type="dialog",
            text="👋 Здравствуйте!\n\nЯ бот для изучения английских и китайских фраз.\n\nВыберите действие:",
            buttons=main_keyboard(),
        )
        return jsonify({"ok": True}), 200

    # --- Обычные сообщения ---
    if update_type == "message_created":
        msg = data.get("message", {})
        recipient = msg.get("recipient", {})
        sender = msg.get("sender", {})
        body = msg.get("body", {})

        chat_id = recipient.get("chat_id")
        chat_type = recipient.get("chat_type")
        user_id = sender.get("user_id")
        text = (body.get("text") or "").strip()

        if text.startswith("/start"):
            send_message(
                user_id=user_id,
                chat_id=chat_id,
                chat_type=chat_type,
                text="👋 Здравствуйте!\n\nЯ бот для изучения английских и китайских фраз.\n\nВыберите действие:",
                buttons=main_keyboard(),
            )
        else:
            send_message(
                user_id=user_id,
                chat_id=chat_id,
                chat_type=chat_type,
                text="Главное меню:",
                buttons=main_keyboard(),
            )
        return jsonify({"ok": True}), 200

    # --- Callback ---
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

        if not user_id:
            user_id = data.get("user_id")
        if not chat_id:
            chat_id = data.get("chat_id")
        if not chat_type:
            chat_type = data.get("chat_type", "dialog")
        if not user_id and cb.get("user"):
            user_id = cb["user"].get("user_id")

        # Отвечаем на callback
        if callback_id:
            try:
                requests.post(
                    f"{MAX_API}/answers",
                    headers=api_headers(),
                    params={"callback_id": callback_id},
                    json={"notification": "Готово"},
                    timeout=10,
                )
            except Exception as e:
                logger.error(f"Ошибка answers: {e}")

        if user_id:
            text, buttons = handle_callback(user_id, payload)
            send_message(
                user_id=user_id,
                chat_id=chat_id,
                chat_type=chat_type,
                text=text,
                buttons=buttons,
            )
        else:
            logger.error("Не удалось определить user_id")

        return jsonify({"ok": True}), 200

    return jsonify({"ok": True}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "bot": "Phrase Trainer"}), 200


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Задайте MAX_BOT_TOKEN")

    port = int(os.environ.get("PORT", "3000"))
    logger.info(f"🚀 Бот запущен на порту {port}")
    app.run(host="0.0.0.0", port=port)
