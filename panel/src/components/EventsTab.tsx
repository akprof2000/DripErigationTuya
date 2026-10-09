// Вкладка «События»: история DP event из облака + новые события вживую.
import React, { useEffect, useRef, useState } from 'react';
import { View, Text } from '@ray-js/ray';
import { useDevice, useProps } from '@ray-js/panel-sdk';
import { t, parseEvent, eventText } from '@/lib/dp';
import { useBedNames } from '@/lib/hooks';
import { loadEventLog, LoggedEvent } from '@/lib/cloud';
import styles from './common.module.less';

const now = () => {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
};

export default function EventsTab() {
  const devId = useDevice(d => d.devInfo?.devId);
  const live = useProps(p => p.event as string);
  const { names } = useBedNames();
  const [items, setItems] = useState<LoggedEvent[]>([]);
  const first = useRef(true);

  useEffect(() => {
    if (devId) loadEventLog(devId).then(setItems);
  }, [devId]);

  // новое значение DP event, пока вкладка открыта, — сверху ленты
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (live) setItems(prev => [{ timeStr: now(), raw: live }, ...prev]);
  }, [live]);

  const rows = items.map(x => ({ ...x, ev: parseEvent(x.raw) })).filter(x => x.ev);

  return (
    <View className={styles.section}>
      {rows.length === 0 && (
        <Text className={`${styles.muted} ${styles.center}`}>{t('no_events')}</Text>
      )}
      {rows.map((x, i) => (
        <View key={`${x.timeStr}-${i}`} className={styles.eventRow}>
          <Text>{eventText(x.ev!, names)}</Text>
          <Text className={styles.eventTime}>
            {x.timeStr.length > 5 ? x.timeStr.slice(5, 16) : x.timeStr}
          </Text>
        </View>
      ))}
    </View>
  );
}
