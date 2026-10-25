"""Устройства контроллера в «Доме с Алисой» и перевод состояний Tuya ⇄ Яндекс.

Устройства:
  bed_1 … bed_8   кран: вкл = «Всегда вкл», выкл = «Выкл»; влажность
  bed_N_auto      выключатель «<имя> автополив»: вкл = Авто, выкл = Выкл
  bed_N_greenhouse  выключатель «<имя> в парнике»: вкл = Парник (поливает и в дождь), выкл = Выкл
  all             выключатель «Полив»: то же для всех грядок сразу (DP mode_all)
  all_auto, all_greenhouse  «Автополив» / «Полив в парнике» для всех грядок
  drain           выключатель «Дренаж»: включить = разовый пролив (команда drain), выключится сам
  status          датчик «Контроллер полива»: события для сценариев и уведомлений
                    water_level low  — засор фильтра
                    water_leak  leak — авария платы клапанов
                    open opened      — идёт дождь
                    humidity         — минимальная влажность среди включённых грядок
"""

CHANNELS = 8
FAULT_BITS = ["rtc", "sd", "valves", "filter_clog"]   # порядок битов DP fault (spec/dp.json)

ON_OFF = "devices.capabilities.on_off"
FLOAT = "devices.properties.float"
EVENT = "devices.properties.event"
VALVE = "devices.types.openable.valve"   # иконка крана у всего, что пускает воду

# выключатели режимов: суффикс id → (режим Tuya, хвост имени)
MODE_SWITCHES = {"auto": ("auto", "автополив"), "greenhouse": ("greenhouse", "в парнике")}


def _split(device_id):
    """bed_3_auto → ("bed_3", "auto"); all_greenhouse → ("all", "greenhouse"); прочие → (id, None)."""
    for suffix in MODE_SWITCHES:
        if device_id.endswith("_" + suffix):
            return device_id[: -len(suffix) - 1], suffix
    return device_id, None


NAME_MAX = 25   # предел длины имени устройства в «Доме с Алисой»
ALL_NAMES = {"auto": "Автополив", "greenhouse": "Полив в парнике"}


def _switch_name(bed, tail):
    """«Кабачки автополив»; длинное имя грядки обрезается, чтобы влезть в 25 символов."""
    room = NAME_MAX - len(tail) - 1
    return "%s %s" % (bed[:room].rstrip(), tail)


def _mode_code(base):
    return "mode_all" if base == "all" else "mode_%d" % int(base[4:])


def bed_name(status, ch):
    name = (status.get("name_%d" % ch) or "").strip()
    return name or "Растение %d" % ch


def faults(status):
    v = status.get("fault", 0)
    if isinstance(v, list):
        return set(v)
    try:
        v = int(v)
    except (TypeError, ValueError):
        return set()
    return {name for i, name in enumerate(FAULT_BITS) if v & (1 << i)}


def _on_off():
    return {"type": ON_OFF, "retrievable": True, "reportable": True}


def _float(instance, unit):
    return {"type": FLOAT, "retrievable": True, "reportable": True,
            "parameters": {"instance": instance, "unit": unit}}


def _event(instance, events):
    return {"type": EVENT, "retrievable": True, "reportable": True,
            "parameters": {"instance": instance, "events": [{"value": e} for e in events]}}


def devices(status, room="Улица"):
    """Описание устройств для /user/devices."""
    out = []
    for ch in range(1, CHANNELS + 1):
        out.append({
            "id": "bed_%d" % ch,
            "name": bed_name(status, ch),
            "description": "Грядка %d" % ch,
            "room": room,
            "type": VALVE,
            "capabilities": [_on_off()],
            "properties": [_float("humidity", "unit.percent")],
        })
        for suffix, (_, tail) in MODE_SWITCHES.items():
            out.append({"id": "bed_%d_%s" % (ch, suffix), "name": _switch_name(bed_name(status, ch), tail),
                        "room": room, "type": VALVE, "capabilities": [_on_off()]})
    out.append({"id": "all", "name": "Полив", "room": room, "type": VALVE,
                "capabilities": [_on_off()]})
    for suffix, (_, tail) in MODE_SWITCHES.items():
        out.append({"id": "all_" + suffix, "name": ALL_NAMES[suffix], "room": room,
                    "type": VALVE, "capabilities": [_on_off()]})
    out.append({"id": "drain", "name": "Дренаж", "room": room, "type": VALVE,
                "capabilities": [_on_off()]})
    out.append({"id": "status", "name": "Контроллер полива", "room": room, "type": "devices.types.sensor",
                "properties": [_event("water_level", ["low", "normal"]),
                               _event("water_leak", ["dry", "leak"]),
                               _event("open", ["opened", "closed"]),
                               _float("humidity", "unit.percent")]})
    return out


def _cap(ctype, instance, value):
    return {"type": ctype, "state": {"instance": instance, "value": value}}


def _prop(ptype, instance, value):
    return {"type": ptype, "state": {"instance": instance, "value": value}}


def _bed_mode(status, ch):
    return status.get("mode_%d" % ch, "auto")


def state(device_id, status):
    """Текущее состояние одного устройства (capabilities + properties)."""
    base, suffix = _split(device_id)
    if suffix:
        mode = MODE_SWITCHES[suffix][0]
        chans = range(1, CHANNELS + 1) if base == "all" else [int(base[4:])]
        return {"capabilities": [_cap(ON_OFF, "on", all(_bed_mode(status, ch) == mode for ch in chans))]}
    if device_id.startswith("bed_"):
        ch = int(device_id[4:])
        mode = _bed_mode(status, ch)
        return {"capabilities": [_cap(ON_OFF, "on", mode != "off")],
                "properties": [_prop(FLOAT, "humidity", float(status.get("humidity_%d" % ch, 0)))]}
    if device_id == "all":
        modes = [_bed_mode(status, ch) for ch in range(1, CHANNELS + 1)]
        return {"capabilities": [_cap(ON_OFF, "on", any(m != "off" for m in modes))]}
    if device_id == "drain":
        return {"capabilities": [_cap(ON_OFF, "on", bool(status.get("drain")))]}
    if device_id == "status":
        f = faults(status)
        active = [status.get("humidity_%d" % ch, 0) for ch in range(1, CHANNELS + 1)
                  if _bed_mode(status, ch) != "off"]
        return {"properties": [_prop(EVENT, "water_level", "low" if "filter_clog" in f else "normal"),
                               _prop(EVENT, "water_leak", "leak" if "valves" in f else "dry"),
                               _prop(EVENT, "open", "opened" if status.get("rain") else "closed"),
                               _prop(FLOAT, "humidity", float(min(active)) if active else 0.0)]}
    raise KeyError(device_id)


def commands(device_id, capability):
    """Действие Алисы → команды Tuya {code: value}."""
    ctype = capability["type"]
    value = capability["state"]["value"]
    base, suffix = _split(device_id)
    if suffix and ctype == ON_OFF:
        return {_mode_code(base): MODE_SWITCHES[suffix][0] if value else "off"}
    if device_id.startswith("bed_") or device_id == "all":
        code = _mode_code(device_id)
        if ctype == ON_OFF:
            return {code: "on" if value else "off"}
    if device_id == "drain" and ctype == ON_OFF:
        return {"command": "drain"} if value else {}   # выключается сам через 12 с
    raise ValueError("%s: действие %s не поддерживается" % (device_id, ctype))
