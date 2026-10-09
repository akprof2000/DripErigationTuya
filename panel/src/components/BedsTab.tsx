// Вкладка «Грядки»: плашки статуса и карточки 8 каналов (влажность, порог, клапан).
import React from 'react';
import { View, Text, navigateTo } from '@ray-js/ray';
import { CHANNELS, Ch, t, bedName, valveTone, faultsOf } from '@/lib/dp';
import { useChannel, useStatus, useBedNames } from '@/lib/hooks';
import styles from './common.module.less';

function Chip({
  text,
  tone,
}: {
  text: string;
  tone: 'accent' | 'ok' | 'warn' | 'danger' | 'muted';
}) {
  return <Text className={`${styles.chip} ${styles[`chip_${tone}`]}`}>{text}</Text>;
}

function BedCard({ ch, name }: { ch: Ch; name: string }) {
  const { humidity, valve, mode, border } = useChannel(ch);
  const tone = valveTone(valve);
  return (
    <View
      className={styles.card}
      onClick={() => navigateTo({ url: `/pages/channel/index?ch=${ch}` })}
    >
      <View className={styles.row}>
        <Text className={styles.cardTitle}>{name}</Text>
        <Text className={`${styles.dot} ${styles[`dot_${tone}`]}`} />
      </View>
      <Text className={styles.big}>{humidity}%</Text>
      <View className={styles.bar}>
        <View className={styles.barFill} style={{ width: `${humidity}%` }} />
        <View className={styles.barMark} style={{ left: `${border}%` }} />
      </View>
      <Text className={styles.muted}>
        {t(`mode_${mode}`)} · {t(`vs_${valve ?? 'init'}`)}
      </Text>
    </View>
  );
}

export default function BedsTab() {
  const s = useStatus();
  const { names } = useBedNames();
  const faults = faultsOf(s.fault).filter(f => f !== 'filter_clog');

  return (
    <View>
      {faults.length > 0 && (
        <View className={styles.alert}>
          {t('ev_hw_fault', faults.map(f => t(`hw_${f}`)).join(', '))}
        </View>
      )}
      <View className={styles.chips}>
        <Chip text={s.night ? t('night') : t('day')} tone="muted" />
        <Chip text={s.rain ? t('rain') : t('dry')} tone={s.rain ? 'accent' : 'ok'} />
        {s.pump && <Chip text={t('pump')} tone="accent" />}
        {s.drain && <Chip text={t('drain')} tone="warn" />}
        {s.fill && <Chip text={t('fill')} tone="warn" />}
        {s.flowRate > 0 && <Chip text={`${s.flowRate.toFixed(2)} ${t('lpm')}`} tone="accent" />}
      </View>
      <View className={styles.grid}>
        {CHANNELS.map(ch => (
          <BedCard key={ch} ch={ch} name={bedName(names, ch)} />
        ))}
      </View>
    </View>
  );
}
