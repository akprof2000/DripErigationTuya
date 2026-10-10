// Облачные вызовы панели: свойства устройства (названия грядок), журнал DP (лента
// событий и графики по дням). Графики считаются из журнала отчётов DP прямо в
// панели: облачная статистика (getDataWithSpecified) требует платной способности
// «MiniApp Chart Capability», а журнал отчётов доступен бесплатно. Обёрнуты в try/catch: в IDE на
// виртуальном устройстве часть облачных API недоступна, а панель должна работать.
import { getDevProperty, saveDevProperty, getDpReportLog } from '@ray-js/ray';

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

const DAY_MS = 86400000;
const dayKey = (timeStr: string) => timeStr.slice(0, 10).replace(/-/g, ''); // yyyy-MM-dd → yyyyMMdd

type Report = { day: string; hour: number; value: number };

/**
 * Отчёты DP за дни fromDay..toDay (yyyyMMdd), по возрастанию времени. Журнал
 * отдаётся с конца страницами по 1000: листаем (рекурсией), пока не дойдём до
 * дней старше fromDay или до maxPages.
 */
async function loadReports(
  devId: string,
  dpId: number,
  fromDay: string,
  toDay: string,
  maxPages = 12,
  page = 0,
  acc: Report[] = []
): Promise<Report[]> {
  const res = await getDpReportLog({
    devId,
    dpIds: String(dpId),
    offset: page * 1000,
    limit: 1000,
    sortType: 'DESC',
  });
  const rows = (res?.dps ?? []).map(x => ({
    day: dayKey(x.timeStr),
    hour: Number(x.timeStr.slice(11, 13)),
    value: Number(x.value),
  }));
  const fresh = rows.filter(r => r.day >= fromDay && r.day <= toDay);
  const all = acc.concat(fresh);
  const reachedOlder = rows.some(r => r.day < fromDay);
  if (reachedOlder || !res?.hasNext || page + 1 >= maxPages) return all.reverse();
  return loadReports(devId, dpId, fromDay, toDay, maxPages, page + 1, all);
}

export const dayOf = (offsetDays: number) => ymd(new Date(Date.now() - offsetDays * DAY_MS));

/**
 * Средние значения DP по часам за день (yyyyMMdd): 24 точки, null — нет данных.
 * Это «график за день» бота: влажность грядки по часам.
 */
export async function loadHourlyFromLog(
  devId: string,
  dpId: number,
  day: string,
  scale = 0
): Promise<(number | null)[]> {
  try {
    const reports = await loadReports(devId, dpId, day, day);
    const sum = new Array(24).fill(0);
    const cnt = new Array(24).fill(0);
    reports.forEach(r => {
      sum[r.hour] += r.value;
      cnt[r.hour] += 1;
    });
    return sum.map((v, h) => (cnt[h] ? v / cnt[h] / 10 ** scale : null));
  } catch (e) {
    console.warn('loadHourlyFromLog', e);
    return [];
  }
}

/**
 * Значения DP по дням за последние `days` дней из журнала отчётов.
 * mode 'delta' — прирост накопительного счётчика за день (flow_total; сброс
 * счётчика учитывается), 'avg' — среднее за день (влажность). scale — как в spec.
 * Дни без данных: для 'delta' — 0, для 'avg' — пропускаются.
 */
export async function loadDailyFromLog(
  devId: string,
  dpId: number,
  days: number,
  mode: 'delta' | 'avg',
  scale = 0
): Promise<{ day: string; value: number }[]> {
  try {
    const reports = await loadReports(devId, dpId, dayOf(days - 1), dayOf(0));
    const k = 10 ** scale;
    const sum: Record<string, number> = {};
    const cnt: Record<string, number> = {};
    reports.reduce<number | undefined>((prev, r) => {
      if (mode === 'delta') {
        if (prev !== undefined)
          sum[r.day] = (sum[r.day] ?? 0) + (r.value >= prev ? r.value - prev : r.value);
      } else {
        sum[r.day] = (sum[r.day] ?? 0) + r.value;
        cnt[r.day] = (cnt[r.day] ?? 0) + 1;
      }
      return r.value;
    }, undefined);
    const lastDays = Array.from({ length: days }, (_, i) =>
      ymd(new Date(Date.now() - (days - 1 - i) * DAY_MS))
    );
    const result =
      mode === 'delta'
        ? lastDays.map(day => ({ day, value: (sum[day] ?? 0) / k }))
        : lastDays.filter(day => cnt[day]).map(day => ({ day, value: sum[day] / cnt[day] / k }));
    return result;
  } catch (e) {
    console.warn('loadDailyFromLog', e);
    return [];
  }
}
