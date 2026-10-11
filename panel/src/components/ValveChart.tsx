// Ступенчатый график клапана за день: «Открыт / Закрыт» по оси Y, часы по X.
// Рисуется из интервалов открытия (lib/cloud.ts loadValveDay) абсолютными View в процентах.
import React from 'react';
import { View, Text } from '@ray-js/ray';
import { t } from '@/lib/dp';
import styles from './chart.module.less';

type Props = { intervals: [number, number][]; end: number };

const pct = (x: number) => `${(x * 100).toFixed(3)}%`;

export default function ValveChart({ intervals, end }: Props) {
  // закрытые участки — между открытыми, до «конца» (для сегодня — сейчас)
  const closed: [number, number][] = [];
  let at = 0;
  intervals.forEach(([a, b]) => {
    if (a > at) closed.push([at, a]);
    at = b;
  });
  if (end > at) closed.push([at, end]);
  return (
    <View className={styles.wrap}>
      <View className={`${styles.axis} ${styles.axisValve}`}>
        <Text className={styles.tick}>{t('valve_open')}</Text>
        <Text className={styles.tick}>{t('valve_closed')}</Text>
      </View>
      <View className={styles.plot}>
        <View className={styles.gridTop} />
        <View className={`${styles.bars} ${styles.valvePlot}`}>
          {closed.map(([a, b]) => (
            <View key={`c${a}`} className={styles.stepLow} style={{ left: pct(a), width: pct(b - a) }} />
          ))}
          {intervals.map(([a, b]) => (
            <View
              key={`o${a}`}
              className={styles.stepHigh}
              style={{ left: pct(a), width: pct(Math.max(b - a, 0.002)) }}
            />
          ))}
        </View>
        <View className={styles.labels}>
          {[0, 6, 12, 18].map(h => (
            <Text key={h} className={styles.label}>{`${String(h).padStart(2, '0')}:00`}</Text>
          ))}
        </View>
      </View>
    </View>
  );
}
