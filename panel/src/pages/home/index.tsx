// Главный экран: четыре вкладки по макету — Грядки, Вода, События, Настройки.
import React, { useState } from 'react';
import { View } from '@ray-js/ray';
import { NavBar, Tabbar, TabbarItem } from '@ray-js/smart-ui';
import { useDevice } from '@ray-js/panel-sdk';
import { t } from '@/lib/dp';
import BedsTab from '@/components/BedsTab';
import WaterTab from '@/components/WaterTab';
import EventsTab from '@/components/EventsTab';
import SettingsTab from '@/components/SettingsTab';
import styles from './index.module.less';

const TABS = ['beds', 'water', 'events', 'settings'] as const;
type Tab = (typeof TABS)[number];

export function Home() {
  const [tab, setTab] = useState<Tab>('beds');
  const title = useDevice(d => d.devInfo?.name) || 'Drip Irrigation';

  return (
    <View className={styles.page}>
      <NavBar title={title} />
      <View className={styles.body}>
        {tab === 'beds' && <BedsTab />}
        {tab === 'water' && <WaterTab />}
        {tab === 'events' && <EventsTab />}
        {tab === 'settings' && <SettingsTab />}
      </View>
      <Tabbar active={TABS.indexOf(tab)} onChange={(e: any) => setTab(TABS[Number(e.detail)])}>
        {TABS.map(k => (
          <TabbarItem key={k}>{t(`tab_${k}`)}</TabbarItem>
        ))}
      </Tabbar>
    </View>
  );
}

export default Home;
