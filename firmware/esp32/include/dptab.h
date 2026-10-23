// dptab.h 📋 Таблица DP из spec/dp.json. Сгенерировано tools/gen_dptab.py, руками не править.
// Канальные DP раскрыты: id = base + N, code = code_N, channel = N (N = 1..8).
#pragma once
#include "dp.h"

// Допустимые значения enum (по имени диапазона из dp.json)
static const char* const DP_ENUM_mode[] = {"auto", "on", "off", "greenhouse"};
static const char* const DP_ENUM_valve_state[] = {"init", "open_hum", "close_hum", "hyst", "forced_open", "forced_close"};
static const char* const DP_ENUM_command[] = {"restart", "reset_settings", "clear_flow", "filter_cleaned", "drain"};
static const char* const DP_ENUM_pump_state[] = {"off", "start", "valves", "drain"};

// Имена битов bitmap/fault (по коду DP)
static const char* const DP_LABELS_fault[] = {"rtc", "sd", "valves", "filter_clog"};

// id, code, type, mode, min, max, scale, range, rangeLen, labels, labelsLen, maxlen, channel
static const DpInfo DP_TABLE[] = {
  {101, "rain", DpType::Bool, DpMode::RO, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // Дождь
  {102, "night", DpType::Bool, DpMode::RO, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // Ночь
  {103, "pump", DpType::Bool, DpMode::RO, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // Насос включён
  {104, "drain", DpType::Bool, DpMode::RO, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // Идёт пролив дренажа
  {105, "fill", DpType::Bool, DpMode::RO, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // Идёт заливка бака
  {106, "flow_rate", DpType::Value, DpMode::RO, 0, 100000, 3, nullptr, 0, nullptr, 0, 255, 0},  // Скорость потока [л/мин]
  {107, "flow_session", DpType::Value, DpMode::RO, 0, 10000000, 2, nullptr, 0, nullptr, 0, 255, 0},  // Расход за сессию [л]
  {108, "flow_total", DpType::Value, DpMode::RO, 0, 100000000, 1, nullptr, 0, nullptr, 0, 255, 0},  // Расход всего [л]
  {109, "fault", DpType::Fault, DpMode::RO, 0, 0, 0, nullptr, 0, DP_LABELS_fault, 4, 255, 0},  // Неисправности
  {110, "filter_baseline", DpType::Value, DpMode::RO, 0, 100000, 3, nullptr, 0, nullptr, 0, 255, 0},  // Эталон потока на клапан [л/мин]
  {111, "run_on_rain", DpType::Bool, DpMode::RW, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // Работать в дождь
  {112, "run_on_night", DpType::Bool, DpMode::RW, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // Работать ночью
  {113, "delta_hum", DpType::Value, DpMode::RW, 0, 50, 0, nullptr, 0, nullptr, 0, 255, 0},  // Гистерезис влажности [%]
  {114, "delta_calib", DpType::Value, DpMode::RW, 0, 500, 0, nullptr, 0, nullptr, 0, 255, 0},  // Дельта калибровки [АЦП]
  {115, "boost_pump_valves", DpType::Value, DpMode::RW, 1, 9, 0, nullptr, 0, nullptr, 0, 255, 0},  // Насос давления: от N клапанов (9 = выкл)
  {116, "clog_threshold", DpType::Value, DpMode::RW, 10, 95, 0, nullptr, 0, nullptr, 0, 255, 0},  // Порог засора фильтра [%]
  {117, "flow_monitor", DpType::Bool, DpMode::RW, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // Контроль засора фильтра
  {118, "autocal_no_delay", DpType::Bool, DpMode::RW, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // Авто-калибровка без задержки
  {119, "command", DpType::Enum, DpMode::WR, 0, 0, 0, DP_ENUM_command, 5, nullptr, 0, 255, 0},  // Команда
  {120, "mode_all", DpType::Enum, DpMode::WR, 0, 0, 0, DP_ENUM_mode, 4, nullptr, 0, 255, 0},  // Режим всех каналов
  {121, "wizard", DpType::String, DpMode::WR, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // Мастер: команда (JSON)
  {122, "wizard_state", DpType::String, DpMode::RO, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // Мастер: состояние (JSON)
  {123, "adc_raw", DpType::Raw, DpMode::RO, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // АЦП каналов: 8 × (тек, мин, макс), uint16 BE
  {124, "event", DpType::String, DpMode::RO, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // Событие (JSON с кодом, лента вместо уведомлений Telegram)
  {125, "pump_state", DpType::Enum, DpMode::RO, 0, 0, 0, DP_ENUM_pump_state, 4, nullptr, 0, 255, 0},  // Насос давления: причина работы (off — выключен, start — пусковые 30 с, valves — по порогу открытых клапанов, drain — пролив дренажа)
  {126, "sys_info", DpType::String, DpMode::RO, 0, 0, 0, nullptr, 0, nullptr, 0, 255, 0},  // О контроллере (JSON): fw, up — аптайм с, heap — свободно байт, rssi, t — время устройства, rtc/sd — 1/0, pulses — импульсов расходомера, last_pulse — с назад (-1 если не было), pending — записей в офлайн-очереди
  {127, "pump_start_sec", DpType::Value, DpMode::RW, 0, 600, 0, nullptr, 0, nullptr, 0, 255, 0},  // Пусковое окно насоса: сколько секунд держать насос после открытия клапана (0 — не включать) [с]
  {131, "humidity_1", DpType::Value, DpMode::RO, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 1},  // Влажность 1 [%]
  {132, "humidity_2", DpType::Value, DpMode::RO, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 2},  // Влажность 2 [%]
  {133, "humidity_3", DpType::Value, DpMode::RO, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 3},  // Влажность 3 [%]
  {134, "humidity_4", DpType::Value, DpMode::RO, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 4},  // Влажность 4 [%]
  {135, "humidity_5", DpType::Value, DpMode::RO, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 5},  // Влажность 5 [%]
  {136, "humidity_6", DpType::Value, DpMode::RO, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 6},  // Влажность 6 [%]
  {137, "humidity_7", DpType::Value, DpMode::RO, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 7},  // Влажность 7 [%]
  {138, "humidity_8", DpType::Value, DpMode::RO, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 8},  // Влажность 8 [%]
  {141, "valve_1", DpType::Enum, DpMode::RO, 0, 0, 0, DP_ENUM_valve_state, 6, nullptr, 0, 255, 1},  // Клапан 1
  {142, "valve_2", DpType::Enum, DpMode::RO, 0, 0, 0, DP_ENUM_valve_state, 6, nullptr, 0, 255, 2},  // Клапан 2
  {143, "valve_3", DpType::Enum, DpMode::RO, 0, 0, 0, DP_ENUM_valve_state, 6, nullptr, 0, 255, 3},  // Клапан 3
  {144, "valve_4", DpType::Enum, DpMode::RO, 0, 0, 0, DP_ENUM_valve_state, 6, nullptr, 0, 255, 4},  // Клапан 4
  {145, "valve_5", DpType::Enum, DpMode::RO, 0, 0, 0, DP_ENUM_valve_state, 6, nullptr, 0, 255, 5},  // Клапан 5
  {146, "valve_6", DpType::Enum, DpMode::RO, 0, 0, 0, DP_ENUM_valve_state, 6, nullptr, 0, 255, 6},  // Клапан 6
  {147, "valve_7", DpType::Enum, DpMode::RO, 0, 0, 0, DP_ENUM_valve_state, 6, nullptr, 0, 255, 7},  // Клапан 7
  {148, "valve_8", DpType::Enum, DpMode::RO, 0, 0, 0, DP_ENUM_valve_state, 6, nullptr, 0, 255, 8},  // Клапан 8
  {151, "mode_1", DpType::Enum, DpMode::RW, 0, 0, 0, DP_ENUM_mode, 4, nullptr, 0, 255, 1},  // Режим 1
  {152, "mode_2", DpType::Enum, DpMode::RW, 0, 0, 0, DP_ENUM_mode, 4, nullptr, 0, 255, 2},  // Режим 2
  {153, "mode_3", DpType::Enum, DpMode::RW, 0, 0, 0, DP_ENUM_mode, 4, nullptr, 0, 255, 3},  // Режим 3
  {154, "mode_4", DpType::Enum, DpMode::RW, 0, 0, 0, DP_ENUM_mode, 4, nullptr, 0, 255, 4},  // Режим 4
  {155, "mode_5", DpType::Enum, DpMode::RW, 0, 0, 0, DP_ENUM_mode, 4, nullptr, 0, 255, 5},  // Режим 5
  {156, "mode_6", DpType::Enum, DpMode::RW, 0, 0, 0, DP_ENUM_mode, 4, nullptr, 0, 255, 6},  // Режим 6
  {157, "mode_7", DpType::Enum, DpMode::RW, 0, 0, 0, DP_ENUM_mode, 4, nullptr, 0, 255, 7},  // Режим 7
  {158, "mode_8", DpType::Enum, DpMode::RW, 0, 0, 0, DP_ENUM_mode, 4, nullptr, 0, 255, 8},  // Режим 8
  {161, "border_1", DpType::Value, DpMode::RW, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 1},  // Порог влажности 1 [%]
  {162, "border_2", DpType::Value, DpMode::RW, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 2},  // Порог влажности 2 [%]
  {163, "border_3", DpType::Value, DpMode::RW, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 3},  // Порог влажности 3 [%]
  {164, "border_4", DpType::Value, DpMode::RW, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 4},  // Порог влажности 4 [%]
  {165, "border_5", DpType::Value, DpMode::RW, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 5},  // Порог влажности 5 [%]
  {166, "border_6", DpType::Value, DpMode::RW, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 6},  // Порог влажности 6 [%]
  {167, "border_7", DpType::Value, DpMode::RW, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 7},  // Порог влажности 7 [%]
  {168, "border_8", DpType::Value, DpMode::RW, 0, 100, 0, nullptr, 0, nullptr, 0, 255, 8},  // Порог влажности 8 [%]
};
static const size_t DP_COUNT = sizeof(DP_TABLE) / sizeof(DP_TABLE[0]);  // 59
