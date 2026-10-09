"""gen_dp_doc.py — docs/dp.md из spec/dp.json (запускать после каждой правки спецификации)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mpy" / "lib"))
from spec import Spec  # noqa: E402

MODE = {"ro": "только чтение", "rw": "чтение/запись", "wr": "только запись"}

WIZARD = """
## Мастера (DP 121 `wizard` → DP 122 `wizard_state`)

Диалоги бота (калибровка, поиск датчика, ручная калибровка) стали мастерами.
Панель шлёт команду JSON-строкой в `wizard`, устройство отвечает состоянием в
`wizard_state`. Тексты подсказок рисует панель по `op` и `step`, устройство шлёт
только коды, поэтому JSON всегда влезает в 255 байт.

| Команда панели | Когда | Ответ устройства |
|---|---|---|
| `{"op":"calib","ch":N,"step":"start"}` | всегда | `{"op":"calib","ch":N,"step":"wet"}`: «положите датчик в воду» |
| `{"op":"calib","step":"next"}` | step = wet | `…"step":"dry","wet":АЦП}`: «достаньте и протрите» |
| `{"op":"calib","step":"next"}` | step = dry | `…"step":"finish","dry":АЦП}`: «воткните в почву» |
| `{"op":"calib","step":"finish"}` | step = finish | `{"op":"calib","ch":N,"step":"done","ok":true,"min":…,"max":…}` или `"ok":false,"err":"span"` |
| `{"op":"search","step":"start"}` | всегда | `{"op":"search","step":"wet"}` |
| `{"op":"search","step":"next"}` | wet → dry → done | итог: `"ok":true,"found":N` или `"ok":false,"err":"not_found"` |
| `{"op":"manual","ch":N,"min":A,"max":B}` | всегда | `{"op":"manual","ch":N,"step":"done","ok":true,"min":A,"max":B}` или `"err":"range"` |
| `{"op":"…","step":"cancel"}` | любой шаг | `"step":"done","ok":false,"err":"cancelled"` |

Коды ошибок `err`: `bad_json`, `bad_channel`, `bad_step` (шаг не подходит, мастер
остаётся на месте), `span` (размах вода/сухо < 100 АЦП), `not_found`, `range`,
`cancelled`, `unknown_op`. Пока калибровка или поиск не в `done`/`idle`,
авто-калибровка границ на устройстве приостановлена (как в прошивке).

## `adc_raw` (DP 123)

48 байт: для каналов 1..8 подряд три `uint16` big-endian: текущее АЦП, граница
«вода» (min), граница «сухо» (max). Нужен экрану калибровки и диагностике.

## `event` (DP 124)

JSON с кодом события, отдельным отчётом на каждое событие (облако хранит историю
DP, из неё панель строит ленту). Тексты, названия грядок и перевод подставляет
панель: названия хранятся не в DP, а в облачных свойствах устройства.

| `t` | Поля | Что случилось |
|---|---|---|
| `valve` | `ch`, `s` (состояние клапана), `h` (влажность, %), `w`=1 если закрыт из-за погоды | клапан канала сменил состояние |
| `rain_start` / `rain_end` | | начался / закончился дождь |
| `rain_block` / `rain_resume` / `rain_still` | | полив остановлен из-за дождя / возобновлён / дождь ещё не кончился к утру |
| `night_start` / `day_start` | | наступила ночь / день |
| `night_block` / `night_resume` | | ночной режим включён / выключен |
| `tank_fill` | | импульс заливки бака |
| `drain_start` / `drain_end` | | пролив дренажа |
| `clog` | `r` (поток), `e` (норма), л/мин | засор фильтра |
| `hw_fault` | `f` (список узлов) | аварийный режим, полив остановлен |
| `reboot`, `reset_settings`, `clear_flow`, `filter_cleaned` | | выполнена команда |

## `fault` (DP 109)

Биты: 0 `rtc`, 1 `sd`, 2 `valves` (аппаратные аварии, полив остановлен),
3 `filter_clog` (засор фильтра, полив продолжается).
"""


def main():
    s = Spec()
    lines = ["# Data points устройства", "",
             "Сгенерировано `tools/gen_dp_doc.py` из `spec/dp.json`. Руками не править.", "",
             "| ID | Код | Тип | Доступ | Описание | Диапазон / значения |",
             "|---:|---|---|---|---|---|"]
    for d in s.dps:
        if d.type == "value":
            rng = f"{d.min}…{d.max}" + (f", ×10^-{d.scale}" if d.scale else "") + (f" {d.unit}" if d.unit else "")
        elif d.type == "enum":
            rng = ", ".join(d.range)
        elif d.type in ("bitmap", "fault"):
            rng = ", ".join(f"b{i} {x}" for i, x in enumerate(d.labels))
        elif d.type == "string":
            rng = f"до {d.maxlen} байт UTF-8"
        else:
            rng = ""
        lines.append(f"| {d.id} | `{d.code}` | {d.type} | {MODE[d.mode]} | {d.name} | {rng} |")
    out = ROOT / "docs" / "dp.md"
    out.write_text("\n".join(lines) + "\n" + WIZARD, encoding="utf-8")
    print(f"{out}: {len(s.dps)} DP")


if __name__ == "__main__":
    main()
