# Data points устройства

Сгенерировано `tools/gen_dp_doc.py` из `spec/dp.json`. Руками не править.

| ID | Код | Тип | Доступ | Описание | Диапазон / значения |
|---:|---|---|---|---|---|
| 101 | `rain` | bool | только чтение | Дождь |  |
| 102 | `night` | bool | только чтение | Ночь |  |
| 103 | `pump` | bool | только чтение | Насос включён |  |
| 104 | `drain` | bool | только чтение | Идёт пролив дренажа |  |
| 105 | `fill` | bool | только чтение | Идёт заливка бака |  |
| 106 | `flow_rate` | value | только чтение | Скорость потока | 0…100000, ×10^-3 л/мин |
| 107 | `flow_session` | value | только чтение | Расход за сессию | 0…10000000, ×10^-2 л |
| 108 | `flow_total` | value | только чтение | Расход всего | 0…100000000, ×10^-1 л |
| 109 | `fault` | fault | только чтение | Неисправности | b0 rtc, b1 sd, b2 valves, b3 filter_clog |
| 110 | `filter_baseline` | value | только чтение | Эталон потока на клапан | 0…100000, ×10^-3 л/мин |
| 111 | `run_on_rain` | bool | чтение/запись | Работать в дождь |  |
| 112 | `run_on_night` | bool | чтение/запись | Работать ночью |  |
| 113 | `delta_hum` | value | чтение/запись | Гистерезис влажности | 0…50 % |
| 114 | `delta_calib` | value | чтение/запись | Дельта калибровки | 0…500 АЦП |
| 115 | `boost_pump_valves` | value | чтение/запись | Насос давления: от N клапанов (9 = выкл) | 1…9 |
| 116 | `clog_threshold` | value | чтение/запись | Порог засора фильтра | 10…95 % |
| 117 | `flow_monitor` | bool | чтение/запись | Контроль засора фильтра |  |
| 118 | `autocal_no_delay` | bool | чтение/запись | Авто-калибровка без задержки |  |
| 119 | `command` | enum | только запись | Команда | restart, reset_settings, clear_flow, filter_cleaned |
| 120 | `mode_all` | enum | только запись | Режим всех каналов | auto, on, off, greenhouse |
| 121 | `wizard` | string | только запись | Мастер: команда (JSON) | до 255 байт UTF-8 |
| 122 | `wizard_state` | string | только чтение | Мастер: состояние (JSON) | до 255 байт UTF-8 |
| 123 | `adc_raw` | raw | только чтение | АЦП каналов: 8 × (тек, мин, макс), uint16 BE |  |
| 124 | `event` | string | только чтение | Событие (JSON с кодом, лента вместо уведомлений Telegram) | до 255 байт UTF-8 |
| 131 | `humidity_1` | value | только чтение | Влажность 1 | 0…100 % |
| 132 | `humidity_2` | value | только чтение | Влажность 2 | 0…100 % |
| 133 | `humidity_3` | value | только чтение | Влажность 3 | 0…100 % |
| 134 | `humidity_4` | value | только чтение | Влажность 4 | 0…100 % |
| 135 | `humidity_5` | value | только чтение | Влажность 5 | 0…100 % |
| 136 | `humidity_6` | value | только чтение | Влажность 6 | 0…100 % |
| 137 | `humidity_7` | value | только чтение | Влажность 7 | 0…100 % |
| 138 | `humidity_8` | value | только чтение | Влажность 8 | 0…100 % |
| 141 | `valve_1` | enum | только чтение | Клапан 1 | init, open_hum, close_hum, hyst, forced_open, forced_close |
| 142 | `valve_2` | enum | только чтение | Клапан 2 | init, open_hum, close_hum, hyst, forced_open, forced_close |
| 143 | `valve_3` | enum | только чтение | Клапан 3 | init, open_hum, close_hum, hyst, forced_open, forced_close |
| 144 | `valve_4` | enum | только чтение | Клапан 4 | init, open_hum, close_hum, hyst, forced_open, forced_close |
| 145 | `valve_5` | enum | только чтение | Клапан 5 | init, open_hum, close_hum, hyst, forced_open, forced_close |
| 146 | `valve_6` | enum | только чтение | Клапан 6 | init, open_hum, close_hum, hyst, forced_open, forced_close |
| 147 | `valve_7` | enum | только чтение | Клапан 7 | init, open_hum, close_hum, hyst, forced_open, forced_close |
| 148 | `valve_8` | enum | только чтение | Клапан 8 | init, open_hum, close_hum, hyst, forced_open, forced_close |
| 151 | `mode_1` | enum | чтение/запись | Режим 1 | auto, on, off, greenhouse |
| 152 | `mode_2` | enum | чтение/запись | Режим 2 | auto, on, off, greenhouse |
| 153 | `mode_3` | enum | чтение/запись | Режим 3 | auto, on, off, greenhouse |
| 154 | `mode_4` | enum | чтение/запись | Режим 4 | auto, on, off, greenhouse |
| 155 | `mode_5` | enum | чтение/запись | Режим 5 | auto, on, off, greenhouse |
| 156 | `mode_6` | enum | чтение/запись | Режим 6 | auto, on, off, greenhouse |
| 157 | `mode_7` | enum | чтение/запись | Режим 7 | auto, on, off, greenhouse |
| 158 | `mode_8` | enum | чтение/запись | Режим 8 | auto, on, off, greenhouse |
| 161 | `border_1` | value | чтение/запись | Порог влажности 1 | 0…100 % |
| 162 | `border_2` | value | чтение/запись | Порог влажности 2 | 0…100 % |
| 163 | `border_3` | value | чтение/запись | Порог влажности 3 | 0…100 % |
| 164 | `border_4` | value | чтение/запись | Порог влажности 4 | 0…100 % |
| 165 | `border_5` | value | чтение/запись | Порог влажности 5 | 0…100 % |
| 166 | `border_6` | value | чтение/запись | Порог влажности 6 | 0…100 % |
| 167 | `border_7` | value | чтение/запись | Порог влажности 7 | 0…100 % |
| 168 | `border_8` | value | чтение/запись | Порог влажности 8 | 0…100 % |

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
