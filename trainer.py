import os
import random


class Trainer:
    """Тренажёр фраз для одного пользователя и одного языка."""

    def __init__(self, user_id, language, template_path, user_dir, learned_count=3, variants_count=4):
        """
        user_id — ID пользователя
        language — 'english' или 'chinese'
        template_path — путь к шаблону (data/english.txt)
        user_dir — папка для файлов пользователей
        learned_count — сколько правильных ответов нужно для "выучено"
        variants_count — сколько вариантов в вопросе
        """
        self.user_id = user_id
        self.language = language
        self.learned_count = learned_count
        self.variants_count = variants_count

        self.file_path = os.path.join(user_dir, f"{user_id}_{language}.txt")

        # Если файла пользователя нет — копируем шаблон
        if not os.path.exists(self.file_path):
            with open(template_path, "r", encoding="utf-8") as src:
                content = src.read()
            with open(self.file_path, "w", encoding="utf-8") as dst:
                dst.write(content)

        self.dictionary = self._load()

    def _load(self):
        """Загрузить словарь из файла."""
        words = []
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) < 4:
                    continue
                words.append({
                    "original": parts[0],
                    "translate": parts[1],
                    "theme": parts[2],
                    "count": int(parts[3]) if parts[3].isdigit() else 0,
                })
        return words

    def _save(self):
        """Сохранить словарь в файл."""
        lines = []
        for w in self.dictionary:
            lines.append(f"{w['original']}|{w['translate']}|{w['theme']}|{w['count']}")
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def get_themes(self):
        """Список всех тем."""
        themes = []
        for w in self.dictionary:
            if w["theme"] not in themes:
                themes.append(w["theme"])
        return themes

    def get_statistic(self):
        """Общая статистика по языку."""
        total = len(self.dictionary)
        learned = sum(1 for w in self.dictionary if w["count"] >= self.learned_count)
        percent = (learned * 100) // total if total > 0 else 0
        return {
            "total": total,
            "learned": learned,
            "percent": percent,
        }

    def get_next_question(self, theme):
        """Следующий вопрос по теме.
        Возвращает dict:
        {
            'question': текст вопроса,
            'variants': [варианты],
            'correct_index': индекс правильного,
            'original': оригинал (для проверки),
            'translate': перевод,
            'reversed': True/False (направление)
        }
        """
        # Фильтруем по теме
        theme_words = [w for w in self.dictionary if w["theme"] == theme]
        if not theme_words:
            return None

        # Невыученные
        not_learned = [w for w in theme_words if w["count"] < self.learned_count]
        if not not_learned:
            return None

        # Определяем направление случайно
        reversed_mode = random.choice([True, False])

        # Выбираем правильный ответ
        correct = random.choice(not_learned)

        # Собираем варианты
        variants_pool = [w for w in theme_words if w != correct]
        random.shuffle(variants_pool)
        variants = [correct] + variants_pool[: self.variants_count - 1]
        random.shuffle(variants)

        correct_index = variants.index(correct)

        # Формируем текст вопроса
        if reversed_mode:
            # Показываем перевод, варианты — оригиналы
            question_text = correct["translate"]
            variant_texts = [w["original"] for w in variants]
        else:
            # Показываем оригинал, варианты — переводы
            question_text = correct["original"]
            variant_texts = [w["translate"] for w in variants]

        return {
            "question": question_text,
            "variants": variant_texts,
            "correct_index": correct_index,
            "original": correct["original"],
            "translate": correct["translate"],
            "reversed": reversed_mode,
        }

    def check_answer(self, original, translate, user_index, correct_index):
        """Проверить ответ и обновить счётчик."""
        if user_index == correct_index:
            # Находим слово и увеличиваем счётчик
            for w in self.dictionary:
                if w["original"] == original and w["translate"] == translate:
                    w["count"] += 1
                    break
            self._save()
            return True
        return False

    def reset_progress(self):
        """Сбросить прогресс."""
        for w in self.dictionary:
            w["count"] = 0
        self._save()
