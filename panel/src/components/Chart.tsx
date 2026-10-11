// График на чистых View: без облачной статистики и без canvas.
// Значения уже посчитаны (lib/cloud.ts), здесь только рисуем: столбики или линию
// с заливкой, сетка, подписи по оси X, при необходимости метка порога.
// Линия — повёрнутые отрезки между точками; для угла нужен размер области в px,
// его даёт createSelectorQuery после отрисовки.
import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, createSelectorQuery } from '@ray-js/ray';
import styles from './chart.module.less';

export type ChartPoint = { label: string; value: number | null; title?: string };

type Props = {
  points: ChartPoint[];
  max?: number; // верх шкалы; по умолчанию — максимум данных
  unit?: string;
  threshold?: number; // горизонтальная линия (порог влажности)
  labelEvery?: number; // подписывать каждую N-ю точку (для 24 часов — 6)
  showValues?: boolean; // значение над каждым столбиком (для 7 дней)
  line?: boolean; // линия с заливкой вместо столбиков
};

let seq = 0;

const fmt = (v: number) => (v >= 10 || Number.isInteger(v) ? String(Math.round(v)) : v.toFixed(1));

export default function Chart({
  points,
  max,
  unit,
  threshold,
  labelEvery = 1,
  showValues = false,
  line = false,
}: Props) {
  const id = useMemo(() => `chart${++seq}`, []);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {
    if (!line) return;
    const q = createSelectorQuery();
    q.select(`#${id}`)
      .boundingClientRect((r: any) => r && r.width && setSize({ w: r.width, h: r.height }))
      .exec(() => undefined);
  }, [line, id, points.length]);
  const top = Math.max(1, max ?? Math.max(...points.map(p => p.value ?? 0)));
  const n = points.length || 1;
  const xy = (i: number, v: number) =>
    size ? { x: ((i + 0.5) / n) * size.w, y: size.h * (1 - v / top) } : { x: 0, y: 0 };
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
        {line ? (
          <View id={id} className={styles.bars}>
            {size &&
              points.map((p, i) => {
                if (p.value === null) return null;
                const a = xy(i, p.value);
                const els = [
                  <View
                    key={`f${i}`}
                    className={styles.fill}
                    style={{
                      left: `${a.x - size.w / n / 2}px`,
                      width: `${size.w / n + 0.5}px`,
                      top: `${a.y}px`,
                    }}
                  />,
                ];
                const next = points[i + 1]?.value;
                if (next !== null && next !== undefined) {
                  const b = xy(i + 1, next);
                  const len = Math.hypot(b.x - a.x, b.y - a.y);
                  const ang = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;
                  els.push(
                    <View
                      key={`s${i}`}
                      className={styles.seg}
                      style={{
                        left: `${a.x}px`,
                        top: `${a.y}px`,
                        width: `${len}px`,
                        transform: `rotate(${ang}deg)`,
                      }}
                    />
                  );
                } else {
                  els.push(
                    <View key={`d${i}`} className={styles.dot} style={{ left: `${a.x}px`, top: `${a.y}px` }} />
                  );
                }
                return els;
              })}
          </View>
        ) : (
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
        )}
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
