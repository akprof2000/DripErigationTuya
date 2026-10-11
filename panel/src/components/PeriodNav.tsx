// Выбор периода графика: ‹ [📅 день или диапазон] ›. Стрелки сдвигают на длину
// периода (день / 7 / 30 дней), по нажатию на дату — календарь снизу.
// Кнопки календаря свои: тулбар smart-ui оставлял «Cancel» по-английски.
import React, { useState } from 'react';
import { View, Text } from '@ray-js/ray';
import { Popup, DateTimePicker } from '@ray-js/smart-ui';
import { t } from '@/lib/dp';
import { dayOf } from '@/lib/cloud';
import styles from './common.module.less';
import chartStyles from './chart.module.less';

export const MAX_BACK = 90; // на сколько дней назад можно уйти

const DAY_MS = 86400000;
const midnight = (ts: number) => {
  const d = new Date(ts);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
};
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
  const [draft, setDraft] = useState(() => midnight(Date.now()));
  const set = (b: number) => onChange(Math.min(MAX_BACK, Math.max(0, b)));

  let title: string;
  if (span > 1) title = `${short(back + span - 1)} – ${short(back)}`;
  else if (back === 0) title = t('today');
  else if (back === 1) title = t('yesterday');
  else title = `${short(back)}.${dayOf(back).slice(0, 4)}`;

  const show = () => {
    setDraft(midnight(Date.now() - back * DAY_MS));
    setOpen(true);
  };
  const apply = () => {
    set(Math.round((midnight(Date.now()) - midnight(draft)) / DAY_MS));
    setOpen(false);
  };

  return (
    <View className={`${styles.row} ${chartStyles.dayRow}`}>
      <Text className={styles.navBtn} onClick={() => set(back + span)}>
        {'<'}
      </Text>
      <Text className={chartStyles.datePick} onClick={show}>
        📅 {title}
      </Text>
      <Text
        className={`${styles.navBtn} ${back === 0 ? chartStyles.navOff : ''}`}
        onClick={() => set(back - span)}
      >
        {'>'}
      </Text>
      <Popup show={open} position="bottom" round onClose={() => setOpen(false)}>
        <View className={chartStyles.pickBar}>
          <Text className={chartStyles.pickCancel} onClick={() => setOpen(false)}>
            {t('cancel')}
          </Text>
          <Text className={chartStyles.pickTitle}>{t(span > 1 ? 'pick_end' : 'pick_day')}</Text>
          <Text className={chartStyles.pickOk} onClick={apply}>
            {t('confirm_yes')}
          </Text>
        </View>
        {open && (
          <DateTimePicker
            type="date"
            value={draft}
            minDate={midnight(Date.now() - MAX_BACK * DAY_MS)}
            maxDate={midnight(Date.now()) + DAY_MS - 1}
            showToolbar={false}
            onInput={(e: any) => {
              const v = Number(e?.detail);
              if (v > 0) setDraft(v);
            }}
          />
        )}
      </Popup>
    </View>
  );
}
