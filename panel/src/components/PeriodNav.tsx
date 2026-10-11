// Выбор периода графика: ‹ [📅 день или диапазон] ›. Стрелки сдвигают на длину
// периода (день / 7 / 30 дней), по нажатию на дату — календарь-сетка месяца снизу.
// Календарь свой: у DateTimePicker из smart-ui тулбар оставался с «Cancel».
import React, { useState } from 'react';
import { View, Text } from '@ray-js/ray';
import { Popup } from '@ray-js/smart-ui';
import { t } from '@/lib/dp';
import { dayOf } from '@/lib/cloud';
import styles from './common.module.less';
import chartStyles from './chart.module.less';

export const MAX_BACK = 90; // на сколько дней назад можно уйти

const DAY_MS = 86400000;
const midnight = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const backOf = (d: Date) =>
  Math.round((midnight(new Date()).getTime() - midnight(d).getTime()) / DAY_MS);
const short = (back: number) => {
  const d = dayOf(back);
  return `${d.slice(6)}.${d.slice(4, 6)}`;
};

type Props = {
  back: number; // последний день периода: 0 — сегодня
  span: number; // длина периода в днях
  onChange: (back: number) => void;
};

export default function PeriodNav({ back, span, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(() => new Date()); // показываемый месяц (любой день в нём)
  const set = (b: number) => onChange(Math.min(MAX_BACK, Math.max(0, b)));

  let title: string;
  if (span > 1) title = `${short(back + span - 1)} – ${short(back)}`;
  else if (back === 0) title = t('today');
  else if (back === 1) title = t('yesterday');
  else title = `${short(back)}.${dayOf(back).slice(0, 4)}`;

  const show = () => {
    setMonth(new Date(Date.now() - back * DAY_MS));
    setOpen(true);
  };
  const pick = (d: Date) => {
    set(backOf(d));
    setOpen(false);
  };

  // сетка месяца: пустые клетки до понедельника первой недели
  const y = month.getFullYear();
  const m = month.getMonth();
  const first = new Date(y, m, 1);
  const lead = (first.getDay() + 6) % 7;
  const days = new Date(y, m + 1, 0).getDate();
  const cells: (Date | null)[] = [
    ...Array.from({ length: lead }, () => null),
    ...Array.from({ length: days }, (_, i) => new Date(y, m, i + 1)),
  ];
  const canPrev = backOf(new Date(y, m, 0)) <= MAX_BACK; // последний день прошлого месяца в пределах
  const canNext = backOf(new Date(y, m + 1, 1)) >= 0; // первый день следующего месяца не в будущем
  const months = t('months').split(',');
  const weekdays = t('weekdays').split(',');

  return (
    <View>
      <View className={chartStyles.navRow}>
        <Text className={chartStyles.datePick} onClick={show}>
          {title}
        </Text>
        <View className={chartStyles.navArrows}>
          <Text className={chartStyles.arrowBtn} onClick={() => set(back + span)}>
            ‹
          </Text>
          <Text
            className={`${chartStyles.arrowBtn} ${back === 0 ? chartStyles.navOff : ''}`}
            onClick={() => set(back - span)}
          >
            ›
          </Text>
        </View>
      </View>
      <Popup show={open} position="bottom" round onClose={() => setOpen(false)}>
        <View className={chartStyles.cal}>
          <View className={chartStyles.pickBar}>
            <Text className={chartStyles.pickCancel} onClick={() => setOpen(false)}>
              {t('btn_cancel')}
            </Text>
            <Text className={chartStyles.pickTitle}>{t(span > 1 ? 'pick_end' : 'pick_day')}</Text>
            <Text className={chartStyles.pickCancel} />
          </View>
          <View className={chartStyles.calHead}>
            <Text
              className={`${styles.navBtn} ${canPrev ? '' : chartStyles.navOff}`}
              onClick={() => canPrev && setMonth(new Date(y, m - 1, 1))}
            >
              {'<'}
            </Text>
            <Text className={chartStyles.calMonth}>{`${months[m]} ${y}`}</Text>
            <Text
              className={`${styles.navBtn} ${canNext ? '' : chartStyles.navOff}`}
              onClick={() => canNext && setMonth(new Date(y, m + 1, 1))}
            >
              {'>'}
            </Text>
          </View>
          <View className={chartStyles.calGrid}>
            {weekdays.map(w => (
              <Text key={w} className={chartStyles.calWd}>
                {w}
              </Text>
            ))}
            {cells.map((d, i) => {
              if (!d) return <View key={`e${i}`} className={chartStyles.calCell} />;
              const b = backOf(d);
              const ok = b >= 0 && b <= MAX_BACK;
              const inPeriod = b >= back && b < back + span;
              return (
                <Text
                  key={`d${i}`}
                  className={`${chartStyles.calCell} ${ok ? '' : chartStyles.calOff} ${
                    inPeriod ? chartStyles.calSel : ''
                  } ${b === 0 ? chartStyles.calToday : ''}`}
                  onClick={() => ok && pick(d)}
                >
                  {d.getDate()}
                </Text>
              );
            })}
          </View>
        </View>
      </Popup>
    </View>
  );
}
