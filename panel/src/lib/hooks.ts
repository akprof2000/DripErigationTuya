// Хуки панели поверх SDM: чтение DP в «человеческом» виде и названия грядок.
import { useEffect, useState, useCallback } from 'react';
import { useProps, useDevice, useActions } from '@ray-js/panel-sdk';
import { Ch, scaled, parseSysInfo } from './dp';
import { loadNames, saveNames } from './cloud';

/** Все DP одной грядки. */
export function useChannel(ch: Ch) {
  const humidity = useProps(p => p[`humidity_${ch}`] as number) ?? 0;
  const valve = useProps(p => p[`valve_${ch}`] as string);
  const mode = useProps(p => p[`mode_${ch}`] as string);
  const border = useProps(p => p[`border_${ch}`] as number) ?? 0;
  return { humidity, valve, mode, border };
}

/** Общий статус контроллера. */
export function useStatus() {
  const p = useProps();
  return {
    rain: !!p.rain,
    night: !!p.night,
    pump: !!p.pump,
    drain: !!p.drain,
    fill: !!p.fill,
    flowRate: scaled(p.flow_rate as number, 3),
    flowSession: scaled(p.flow_session as number, 2),
    flowTotal: scaled(p.flow_total as number, 1),
    filterBaseline: scaled(p.filter_baseline as number, 3),
    fault: (p.fault as number) ?? 0,
    pumpState: (p.pump_state as string) ?? (p.pump ? 'valves' : 'off'),
    sys: parseSysInfo(p.sys_info as string),
  };
}

/**
 * Названия грядок. В DP их нет (лимит Tuya на число DP), они лежат в облачных
 * свойствах устройства — общие для всех участников дома.
 */
export function useBedNames() {
  const devId = useDevice(d => d.devInfo?.devId);
  const actions = useActions();
  const [names, setNames] = useState<string[]>([]);

  useEffect(() => {
    if (!devId) return;
    loadNames(devId).then(setNames);
  }, [devId]);

  const rename = useCallback(
    async (ch: number, name: string) => {
      const next = [...names];
      while (next.length < 8) next.push('');
      next[ch - 1] = name.trim();
      setNames(next);
      if (devId) await saveNames(devId, next);
      // на контроллер — для текста push-уведомлений; пусто — «Растение N» по умолчанию
      actions[`name_${ch}`]?.set(next[ch - 1]);
    },
    [names, devId, actions]
  );

  return { names, rename };
}

export interface Plant {
  name: string;
  border: number;
}

/**
 * Справочник растений с контроллера (/plants.ini на SD). DP plants отдаёт одну
 * страницу «стр/всего|Имя=60;Имя=65», остальные страницы запрашиваются через plant_cmd.
 */
export function usePlants() {
  const actions = useActions();
  const raw = useProps(p => p.plants as string) ?? '';
  const [pages, setPages] = useState<Record<number, Plant[]>>({});
  const [total, setTotal] = useState(0);
  // метка времени в команде: облако не пропускает повтор одинакового значения DP
  const ask = useCallback((page: number) => actions.plant_cmd?.set(`list:${page}:${Date.now()}`), [actions]);

  useEffect(() => {
    const m = /^(\d+)\/(\d+)\|(.*)$/.exec(raw);
    if (!m) return;
    const no = Number(m[1]);
    const items = m[3]
      .split(';')
      .map(e => {
        const eq = e.lastIndexOf('=');
        return { name: e.slice(0, eq).trim(), border: Number(e.slice(eq + 1)) };
      })
      .filter(p => p.name && p.border >= 0);
    setTotal(Number(m[2]));
    setPages(prev => ({ ...prev, [no]: items }));
  }, [raw]);

  // догружаем недостающие страницы по одной
  useEffect(() => {
    for (let i = 0; i < total; i++)
      if (!pages[i]) {
        ask(i);
        return;
      }
  }, [pages, total]);

  const plants: Plant[] = [];
  for (let i = 0; i < total; i++) plants.push(...(pages[i] ?? []));
  plants.sort((a, b) => a.name.localeCompare(b.name, 'ru'));

  const reload = useCallback(() => {
    setPages({});
    ask(0);
  }, [ask]);
  const add = useCallback(
    (name: string, border: number) => {
      setPages({});
      actions.plant_cmd?.set(`add:${name.trim()}=${border}`);
    },
    [actions]
  );
  const remove = useCallback(
    (name: string) => {
      setPages({});
      actions.plant_cmd?.set(`del:${name}`);
    },
    [actions]
  );
  return { plants, reload, add, remove };
}
