"""Устройства контроллера в «Доме с Алисой» и перевод состояний Tuya ⇄ Яндекс.

Устройства:
  bed_1 … bed_8   кран: вкл = «Всегда вкл», выкл = «Выкл», режим «авто»/«эко» = Авто/Парник; влажность
  all             выключатель «Полив»: то же для всех грядок сразу (DP mode_all)
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
MODE = "devices.capabilities.mode"
FLOAT = "devices.properties.float"
EVENT = "devices.properties.event"

# режим грядки ⇄ режим Яндекса (instance program); «on»/«off» — через on_off
YA_MODE = {"auto": "auto", "greenhouse": "eco"}
TUYA_MODE = {v: k for k, v in YA_MODE.items()}


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


def _mode_cap(modes):
    return {"type": MODE, "retrievable": True, "reportable": True,
            "parameters": {"instance": "program", "modes": [{"value": m} for m in modes]}}


def _on_off():
    return {"type": ON_OFF, "retrievable": True, "reportable": True}


def _float(instance, unit):
    return {"type": FLOAT, "retrievable": True, "reportable": True,
            "parameters": {"instance": instance, "unit": unit}}


def _event(instance, events):
    return {"type": EVENT, "retrievable": True, "reportable": True,
            "parameters": {"instance": instance, "events": [{"value": e} for e in events]}}


def devices(status, room="Огород"):
    """Описание устройств для /user/devices."""
    out = []
    for ch in range(1, CHANNELS + 1):
        out.append({
            "id": "bed_%d" % ch,
            "name": bed_name(status, ch),
            "description": "Грядка %d" % ch,
            "room": room,
            "type": "devices.types.openable.valve",
            "capabilities": [_on_off(), _mode_cap(["auto", "eco"])],
            "properties": [_float("humidity", "unit.percent")],
        })
    out.append({"id": "all", "name": "Полив", "room": room, "type": "devices.types.switch",
                "capabilities": [_on_off(), _mode_cap(["auto", "eco"])]})
    out.append({"id": "drain", "name": "Дренаж", "room": room, "type": "devices.types.switch",
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
    if device_id.startswith("bed_"):
        ch = int(device_id[4:])
        mode = _bed_mode(status, ch)
        return {"capabilities": [_cap(ON_OFF, "on", mode != "off"),
                                 _cap(MODE, "program", YA_MODE.get(mode, "auto"))],
                "properties": [_prop(FLOAT, "humidity", float(status.get("humidity_%d" % ch, 0)))]}
    if device_id == "all":
        modes = [_bed_mode(status, ch) for ch in range(1, CHANNELS + 1)]
        common = modes[0] if len(set(modes)) == 1 else "auto"
        return {"capabilities": [_cap(ON_OFF, "on", any(m != "off" for m in modes)),
                                 _cap(MODE, "program", YA_MODE.get(common, "auto"))]}
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
    if device_id.startswith("bed_") or device_id == "all":
        code = "mode_all" if device_id == "all" else "mode_%d" % int(device_id[4:])
        if ctype == ON_OFF:
            return {code: "on" if value else "off"}
        if ctype == MODE:
            if value not in TUYA_MODE:
                raise ValueError("режим %s не поддерживается" % value)
            return {code: TUYA_MODE[value]}
    if device_id == "drain" and ctype == ON_OFF:
        return {"command": "drain"} if value else {}   # выключается сам через 12 с
    raise ValueError("%s: действие %s не поддерживается" % (device_id, ctype))
