// Столбчатый график на чистых View: без облачной статистики и без canvas.
// Значения уже посчитаны (lib/cloud.ts), здесь только рисуем: столбики, сетка,
// подписи по оси X, при необходимости горизонтальная метка порога.
import React from 'react';
import { View, Text } from '@ray-js/ray';
import styles from './chart.module.less';

export type ChartPoint = { label: string; value: number | null; title?: string };

type Props = {
  points: ChartPoint[];
  max?: number; // верх шкалы; по умолчанию — максимум данных
  unit?: string;
  threshold?: number; // горизонтальная линия (порог влажности)
  labelEvery?: number; // подписывать каждую N-ю точку (для 24 часов — 6)
  showValues?: boolean; // значение над каждым столбиком (для 7 дней)
};

const fmt = (v: number) => (v >= 10 || Number.isInteger(v) ? String(Math.round(v)) : v.toFixed(1));

export default function Chart({
  points,
  max,
  unit,
  threshold,
  labelEvery = 1,
  showValues = false,
}: Props) {
  const top = Math.max(1, max ?? Math.max(...points.map(p => p.value ?? 0)));
  const ticks = [top, top / 2];
  return (
    <View className={styles.wrap}>
      <View className={styles.axis}>
        {ticks.map(v => (
          <Text key={v} className={styles.tick}>
            {fmt(v)}
            {unit ? ` ${unit}` : ''}
          </Text>
        ))}
        <Text className={styles.tick}>0</Text>
      </View>
      <View className={styles.plot}>
        <View className={styles.gridTop} />
        <View className={styles.gridMid} />
        {threshold !== undefined && (
          <View className={styles.threshold} style={{ bottom: `${(threshold / top) * 100}%` }} />
        )}
        <View className={styles.bars}>
          {points.map((p, i) => (
            <View key={`${p.label}-${i}`} className={styles.col}>
              {showValues && p.value !== null && (
                <Text className={styles.value}>{fmt(p.value)}</Text>
              )}
              <View
                className={`${styles.bar} ${p.value === null ? styles.barEmpty : ''}`}
                style={{ height: `${p.value === null ? 0 : (p.value / top) * 100}%` }}
              />
            </View>
          ))}
        </View>
        <View className={styles.labels}>
          {points.map((p, i) => (
            <Text key={`${p.label}-${i}`} className={styles.label}>
              {i % labelEvery === 0 ? p.label : ''}
            </Text>
          ))}
        </View>
      </View>
    </View>
  );
}
