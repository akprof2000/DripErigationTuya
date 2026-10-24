"""Разговорный навык «Дачный полив»: вопросы о грядках словами.

  «Алиса, спроси у Дачного полива, какая влажность сейчас»      → влажность всех включённых грядок
  «…какая влажность грядки 2» / «…влажность кабачков»   → одна грядка (по номеру или имени)
  «…что растёт на грядке 5» / «…что растёт на первой»   → имя грядки
  «…что где растёт»                                      → список всех грядок
"""
import re

import mapping

NUM_WORDS = {
    1: ("один", "одна", "первой", "первая", "первую", "первом", "перв"),
    2: ("два", "две", "второй", "вторая", "вторую", "втор"),
    3: ("три", "третьей", "третья", "третью", "трет"),
    4: ("четыре", "четвёртой", "четвертой", "четвертая", "четвёрт", "четверт"),
    5: ("пять", "пятой", "пятая", "пятую", "пят"),
    6: ("шесть", "шестой", "шестая", "шестую", "шест"),
    7: ("семь", "седьмой", "седьмая", "седьмую", "седьм"),
    8: ("восемь", "восьмой", "восьмая", "восьмую", "восьм"),
}
MODE_TEXT = {"off": "выключена", "on": "полив всегда включён", "auto": "автополив",
             "greenhouse": "полив в парнике"}
HELP = ("Спросите, например: какая влажность сейчас, какая влажность грядки два, "
        "какая влажность кабачков, что растёт на грядке пять.")


def _norm(text):
    return re.sub(r"[^а-яa-z0-9 ]", " ", text.lower().replace("ё", "е"))


def _stem(word):
    return word[:max(4, len(word) - 2)]   # «кабачков» ~ «кабачки»


def find_bed(text, status):
    """Номер грядки (1…8) из фразы: цифрой, словом («пятой») или именем («кабачков»)."""
    t = _norm(text)
    m = re.search(r"\b([1-8])\b", t)
    if m:
        return int(m.group(1))
    words = t.split()
    for ch, forms in NUM_WORDS.items():
        if any(w == f or (len(f) <= 6 and w.startswith(f)) for w in words for f in forms):
            return ch
    for ch in range(1, mapping.CHANNELS + 1):
        name_words = [_stem(w) for w in _norm(mapping.bed_name(status, ch)).split() if len(w) > 2]
        if name_words and all(any(w.startswith(n) for w in words) for n in name_words):
            return ch
    return None


def _hum(status, ch):
    return int(status.get("humidity_%d" % ch, 0))


def answer(text, status):
    t = _norm(text)
    if not t.strip() or "помощ" in t or "умеешь" in t:
        return "Я рассказываю о грядках полива. " + HELP
    ch = find_bed(text, status)
    humid = "влаж" in t or "сух" in t or "мокр" in t
    if not humid and ("раст" in t or "посаж" in t or "что на" in t):
        if ch:
            return "На грядке %d — %s." % (ch, mapping.bed_name(status, ch))
        return "Грядки: " + "; ".join("%d — %s" % (c, mapping.bed_name(status, c))
                                     for c in range(1, mapping.CHANNELS + 1)) + "."
    if humid or "полив" in t or ch:
        if ch:
            mode = status.get("mode_%d" % ch, "auto")
            tail = "" if mode in ("auto", "greenhouse") else ", %s" % MODE_TEXT.get(mode, mode)
            return "%s, грядка %d: влажность %d %%%s." % (mapping.bed_name(status, ch), ch, _hum(status, ch), tail)
        parts = []
        for c in range(1, mapping.CHANNELS + 1):
            off = status.get("mode_%d" % c, "auto") == "off"
            parts.append("%s %d %%%s" % (mapping.bed_name(status, c), _hum(status, c), " (выключена)" if off else ""))
        return "Влажность сейчас: " + "; ".join(parts) + "."
    return "Не поняла вопрос. " + HELP


def handle(req, status_fn):
    """Запрос Яндекс Диалогов → ответ. status_fn() читает DP контроллера (только когда нужен)."""
    r = req.get("request", {})
    text = r.get("original_utterance") or r.get("command") or ""
    new = req.get("session", {}).get("new", False)
    one_shot = new and bool(text.strip())
    bye = bool({"хватит", "стоп", "выход", "спасибо", "пока"} & set(_norm(text).split()))
    if bye:
        out = "Хорошо, до связи!"
    elif new and not text.strip():
        out = "Привет! Я знаю всё о грядках на даче. " + HELP
    else:
        try:
            out = answer(text, status_fn())
        except Exception:   # облако Tuya или контроллер недоступны
            out = "Не получилось связаться с контроллером полива. Попробуйте позже."
    return {"version": req.get("version", "1.0"),
            # «спроси у …, вопрос» — один ответ и выход; в запущенном навыке — разговор до «хватит»
            "response": {"text": out, "end_session": one_shot or bye}}
