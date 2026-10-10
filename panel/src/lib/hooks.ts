// Хуки панели поверх SDM: чтение DP в «человеческом» виде и названия грядок.
import { useEffect, useState, useCallback } from 'react';
import { useProps, useDevice } from '@ray-js/panel-sdk';
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
    },
    [names, devId]
  );

  return { names, rename };
}
