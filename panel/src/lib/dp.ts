// Разбор значений DP, которые приходят в панель «сырыми» (как их шлёт устройство).
import Strings from '@/i18n';

export const CHANNELS = [1, 2, 3, 4, 5, 6, 7, 8] as const;
export type Ch = (typeof CHANNELS)[number];
export const MODES = ['auto', 'on', 'off', 'greenhouse'] as const;
export type Mode = (typeof MODES)[number];

/** value-DP со сдвигом scale → число (flow_rate 63 при scale 3 → 0.063). */
export const scaled = (v: number | undefined, scale: number) => (v ?? 0) / 10 ** scale;

export const fmt = (s: string, ...args: (string | number)[]) =>
  args.reduce<string>((acc, a, i) => acc.replace(`{${i}}`, String(a)), s);

export const t = (key: string, ...args: (string | number)[]) =>
  fmt(Strings.getLang(key as never), ...args);

/** raw-DP в панели — hex-строка. adc_raw: 8 × (тек, мин, макс), uint16 big-endian. */
export function parseAdcRaw(hex: string | undefined) {
  const out: { cur: number; min: number; max: number }[] = [];
  if (!hex || hex.length < 8 * 12) return out;
  for (let i = 0; i < 8; i++) {
    const at = (k: number) => parseInt(hex.substr((i * 3 + k) * 4, 4), 16);
    out.push({ cur: at(0), min: at(1), max: at(2) });
  }
  return out;
}

/** fault-DP — битовая маска по labels из spec: 0 rtc, 1 sd, 2 valves, 3 filter_clog. */
export const FAULT_BITS = ['rtc', 'sd', 'valves', 'filter_clog'] as const;
export const faultsOf = (v: number | undefined) =>
  FAULT_BITS.filter((_, i) => Math.floor((v ?? 0) / 2 ** i) % 2 === 1);

export type DeviceEvent = {
  t: string;
  ch?: number;
  s?: string;
  h?: number;
  w?: number;
  r?: number;
  e?: number;
  f?: string[];
};

export function parseEvent(raw: string | undefined): DeviceEvent | null {
  if (!raw) return null;
  try {
    const e = JSON.parse(raw);
    return e && typeof e.t === 'string' ? e : null;
  } catch {
    return null;
  }
}

/** Текст события: название грядки берётся из облачных свойств (names). */
export function eventText(e: DeviceEvent, names: string[]) {
  switch (e.t) {
    case 'valve': {
      const state =
        t(`vs_${e.s}`) + (e.h !== undefined ? ` · ${e.h}%` : '') + (e.w ? t('ev_weather') : '');
      return t('ev_valve', bedName(names, e.ch ?? 0), state);
    }
    case 'clog':
      return t('ev_clog', e.r ?? 0, e.e ?? 0);
    case 'hw_fault':
      return t('ev_hw_fault', (e.f ?? []).map(x => t(`hw_${x}`)).join(', '));
    default:
      return t(`ev_${e.t}`);
  }
}

export const bedName = (names: string[], ch: number) => names[ch - 1] || `${t('bed')} ${ch}`;

/** Кружок на карточке грядки: синий — идёт полив, жёлтый — состояние ещё
 *  неизвестно (после старта), зелёный — клапан закрыт, полива нет. */
export function valveTone(state: string | undefined): 'water' | 'unknown' | 'ok' {
  if (state === 'open_hum' || state === 'forced_open') return 'water';
  if (!state || state === 'init') return 'unknown';
  return 'ok';
}

export const isWatering = (state: string | undefined) => valveTone(state) === 'water';

/** DP sys_info — JSON «о контроллере» (docs/dp.md). */
export type SysInfo = {
  fw?: string;
  up?: number;
  heap?: number;
  rssi?: number;
  t?: number;
  rtc?: number;
  sd?: number;
  pulses?: number;
  last_pulse?: number;
  pending?: number;
};

export function parseSysInfo(raw: string | undefined): SysInfo {
  try {
    const v = raw ? JSON.parse(raw) : {};
    return v && typeof v === 'object' ? v : {};
  } catch {
    return {};
  }
}

/** Секунды → «2 д 03:14». */
export function fmtUptime(sec: number | undefined) {
  if (sec === undefined) return '—';
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const hm = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  return d > 0 ? `${d} ${t('days_short')} ${hm}` : hm;
}
