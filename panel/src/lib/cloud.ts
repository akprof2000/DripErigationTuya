// Облачные вызовы панели: свойства устройства (названия грядок), журнал DP (лента
// событий) и дневная статистика DP (графики). Обёрнуты в try/catch: в IDE на
// виртуальном устройстве часть облачных API недоступна, а панель должна работать.
import { getDevProperty, saveDevProperty, getDpReportLog, getDataWithSpecified } from '@ray-js/ray';

const NAMES_CODE = 'bed_names';

export async function loadNames(devId: string): Promise<string[]> {
  try {
    const items = await getDevProperty({ devId, bizType: 0, code: NAMES_CODE });
    const raw = items?.find(x => x.code === NAMES_CODE)?.value;
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.map(String) : [];
  } catch (e) {
    console.warn('loadNames', e);
    return [];
  }
}

export async function saveNames(devId: string, names: string[]) {
  try {
    await saveDevProperty({
      devId,
      bizType: 0,
      propertyList: JSON.stringify([{ code: NAMES_CODE, value: JSON.stringify(names) }]),
    });
  } catch (e) {
    console.warn('saveNames', e);
  }
}

export type LoggedEvent = { timeStr: string; raw: string };

/** Последние значения DP event (124) из облачного журнала отчётов, новые сверху. */
export async function loadEventLog(devId: string, limit = 100): Promise<LoggedEvent[]> {
  try {
    const res = await getDpReportLog({ devId, dpIds: '124', offset: 0, limit, sortType: 'DESC' });
    return (res?.dps ?? []).map(x => ({ timeStr: x.timeStr, raw: String(x.value) }));
  } catch (e) {
    console.warn('loadEventLog', e);
    return [];
  }
}

const ymd = (d: Date) =>
  `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(
    2,
    '0'
  )}`;

/**
 * Дневная статистика DP за последние `days` дней (статистику DP нужно включить в
 * консоли Tuya). type: 'minux' — прирост за день (для накопительного flow_total),
 * 'avg' — среднее (для влажности). Возвращает [{day: 'YYYYMMDD', value}].
 */
export async function loadDaily(
  devId: string,
  dpId: number,
  days: number,
  type: 'sum' | 'minux' | 'avg'
) {
  try {
    const end = new Date();
    const start = new Date(end.getTime() - (days - 1) * 86400000);
    const res = await getDataWithSpecified({
      devId,
      dpId: String(dpId),
      startDay: ymd(start),
      endDay: ymd(end),
      type,
      auto: 2,
    });
    return Object.entries(res?.result ?? {})
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([day, v]) => ({ day, value: v === '#' ? 0 : Number(v) }));
  } catch (e) {
    console.warn('loadDaily', e);
    return [];
  }
}
