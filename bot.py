import os
from trainer import Trainer


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
USERS_DIR = "/app/data/users"

# Создаём папку для пользователей
os.makedirs(USERS_DIR, exist_ok=True)


# Храним состояние каждого пользователя
# user_id: {
#   "language": "english" | "chinese" | None,
#   "theme": "..." | None,
#   "current_question": {...} | None,
# }
user_state = {}


def get_trainer(user_id, language):
    """Получить Trainer для пользователя."""
    template = os.path.join(DATA_DIR, f"{language}.txt")
    return Trainer(user_id, language, template, USERS_DIR)


# ------------------------- КЛАВИАТУРЫ -------------------------

def main_keyboard():
    return [
        [{"type": "callback", "text": "📚 Изучать фразы", "payload": "learn"}],
        [{"type": "callback", "text": "📊 Статистика", "payload": "stats"}],
        [{"type": "callback", "text": "🗑 Сбросить прогресс", "payload": "reset"}],
    ]


def language_keyboard(prefix):
    """Клавиатура выбора языка.
    prefix — например 'learn_lang', 'stats_lang', 'reset_lang'
    """
    return [
        [{"type": "callback", "text": "🇬🇧 Английский", "payload": f"{prefix}_english"}],
        [{"type": "callback", "text": "🇨🇳 Китайский", "payload": f"{prefix}_chinese"}],
        [{"type": "callback", "text": "← Назад", "payload": "menu"}],
    ]


def themes_keyboard(language, themes):
    """Клавиатура выбора темы."""
    buttons = []
    for theme in themes:
        buttons.append([{"type": "callback", "text": theme, "payload": f"theme_{theme}"}])
    buttons.append([{"type": "callback", "text": "← Назад", "payload": "learn"}])
    return buttons


def question_keyboard(variants):
    """Клавиатура вариантов ответа."""
    buttons = []
    for i, v in enumerate(variants):
        buttons.append([{"type": "callback", "text": v, "payload": f"answer_{i}"}])
    buttons.append([{"type": "callback", "text": "← В меню", "payload": "menu"}])
    return buttons


# ------------------------- ОБРАБОТКА -------------------------

def handle_callback(user_id, payload):
    """Обработка нажатия кнопок.
    Возвращает (text, buttons) для отправки.
    """
    state = user_state.setdefault(user_id, {"language": None, "theme": None, "current_question": None})

    # --- Меню ---
    if payload == "menu":
        state["language"] = None
        state["theme"] = None
        state["current_question"] = None
        return ("Главное меню:", main_keyboard())

    # --- Изучать фразы: выбор языка ---
    if payload == "learn":
        return ("Выберите язык:", language_keyboard("learn_lang"))

    if payload.startswith("learn_lang_"):
        lang = payload.replace("learn_lang_", "")
        state["language"] = lang
        trainer = get_trainer(user_id, lang)
        themes = trainer.get_themes()
        return ("Выберите тему:", themes_keyboard(lang, themes))

    # --- Выбор темы ---
    if payload.startswith("theme_"):
        theme = payload.replace("theme_", "")
        state["theme"] = theme
        return next_question(user_id)

    # --- Ответ на вопрос ---
    if payload.startswith("answer_"):
        idx = int(payload.replace("answer_", ""))
        return check_answer(user_id, idx)

    # --- Статистика ---
    if payload == "stats":
        return ("Выберите язык:", language_keyboard("stats_lang"))

    if payload.startswith("stats_lang_"):
        lang = payload.replace("stats_lang_", "")
        trainer = get_trainer(user_id, lang)
        stat = trainer.get_statistic()
        lang_name = "🇬🇧 Английский" if lang == "english" else "🇨🇳 Китайский"
        text = (
            f"{lang_name}\n\n"
            f"Всего фраз: {stat['total']}\n"
            f"Выучено: {stat['learned']}\n"
            f"Прогресс: {stat['percent']}%"
        )
        return (text, [[{"type": "callback", "text": "← В меню", "payload": "menu"}]])

    # --- Сброс ---
    if payload == "reset":
        return ("Сбросить прогресс по обоим языкам?", [
            [{"type": "callback", "text": "✅ Да, сбросить", "payload": "reset_confirm"}],
            [{"type": "callback", "text": "← Отмена", "payload": "menu"}],
        ])

    if payload == "reset_confirm":
        # Сбрасываем оба языка
        for lang in ("english", "chinese"):
            try:
                trainer = get_trainer(user_id, lang)
                trainer.reset_progress()
            except Exception:
                pass
        return ("Прогресс сброшен по обоим языкам.", [[{"type": "callback", "text": "← В меню", "payload": "menu"}]])

    # --- На всякий случай ---
    return ("Главное меню:", main_keyboard())


def next_question(user_id):
    """Сгенерировать следующий вопрос."""
    state = user_state.get(user_id)
    if not state or not state["language"] or not state["theme"]:
        return ("Главное меню:", main_keyboard())

    trainer = get_trainer(user_id, state["language"])
    question = trainer.get_next_question(state["theme"])

    if not question:
        # Все фразы в теме выучены
        return (
            f"🎉 Все фразы в теме «{state['theme']}» выучены!\n\nВыберите другую тему или язык.",
            [[{"type": "callback", "text": "← К темам", "payload": f"learn_lang_{state['language']}"}],
             [{"type": "callback", "text": "← В меню", "payload": "menu"}]]
        )

    state["current_question"] = question

    text = f"❓ {question['question']}\n\nВыберите перевод:"
    return (text, question_keyboard(question["variants"]))


def check_answer(user_id, idx):
    """Проверить ответ."""
    state = user_state.get(user_id)
    if not state or not state["current_question"]:
        return ("Главное меню:", main_keyboard())

    q = state["current_question"]
    trainer = get_trainer(user_id, state["language"])

    correct = trainer.check_answer(
        original=q["original"],
        translate=q["translate"],
        user_index=idx,
        correct_index=q["correct_index"],
    )

    if correct:
        result_text = "✅ Правильно!"
    else:
        correct_variant = q["variants"][q["correct_index"]]
        result_text = f"❌ Неправильно.\n\nПравильный ответ: {correct_variant}"

    # Следующий вопрос
    next_q_text, next_q_buttons = next_question(user_id)

    text = f"{result_text}\n\n➖➖➖\n\n{next_q_text}"
    return (text, next_q_buttons)
