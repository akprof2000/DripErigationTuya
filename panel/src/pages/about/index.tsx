// «О контроллере»: то, что бот показывал в /status и /WaterFlow как диагностику —
// версия прошивки, аптайм, память, Wi-Fi, часы, SD, расходомер, очередь офлайн.
import React from 'react';
import { View, Text, navigateBack } from '@ray-js/ray';
import { NavBar, Cell, CellGroup } from '@ray-js/smart-ui';
import { useDevice } from '@ray-js/panel-sdk';
import { t, fmtUptime, missingPeriph } from '@/lib/dp';
import { useStatus } from '@/lib/hooks';
import styles from '@/components/common.module.less';
import page from '../home/index.module.less';

const fmtTime = (unix: number | undefined) => {
  if (!unix) return '—';
  const d = new Date(unix * 1000);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getDate())}.${p(d.getMonth() + 1)} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

export default function AboutPage() {
  const { sys } = useStatus();
  const devId = useDevice(d => d.devInfo?.devId);
  const online = useDevice(d => d.devInfo?.isOnline);
  const okText = (v: number | undefined) =>
    v === undefined ? '—' : v ? t('periph_ok') : t('periph_missing');
  const missing = missingPeriph(sys);

  return (
    <View className={page.page}>
      <NavBar title={t('about')} leftArrow onClickLeft={() => navigateBack()} />
      <View className={page.body}>
        <CellGroup inset title=" ">
          <Cell title={t('about_fw')} value={sys.fw ?? '—'} />
          <Cell title={t('about_online')} value={online ? t('yes') : t('no')} />
          <Cell title={t('about_uptime')} value={fmtUptime(sys.up)} />
          <Cell
            title={t('about_heap')}
            value={sys.heap === undefined ? '—' : `${Math.round(sys.heap / 1024)} ${t('kb')}`}
          />
          <Cell
            title={t('about_rssi')}
            value={sys.rssi === undefined || sys.rssi === 0 ? '—' : `${sys.rssi} dBm`}
          />
          <Cell title={t('about_time')} value={fmtTime(sys.t)} />
        </CellGroup>
        {missing.length > 0 && (
          <View className={styles.warnBox}>
            {t('periph_notice', missing.map(f => t(`hw_${f}`)).join(', '))}
          </View>
        )}
        <CellGroup inset title={t('periph_title')}>
          <Cell title={t('about_valves')} value={okText(sys.valves)} />
          <Cell title={t('about_sensors')} value={okText(sys.sensors)} />
          <Cell title={t('about_rtc')} value={okText(sys.rtc)} />
          <Cell title={t('about_sd')} value={okText(sys.sd)} />
          <Cell
            title={t('about_flow')}
            value={
              sys.pulses === undefined ? '—' : sys.pulses > 0 ? t('periph_ok') : t('flow_no_pulses')
            }
          />
          <Cell
            title={t('about_pulses')}
            value={sys.pulses === undefined ? '—' : String(sys.pulses)}
          />
          <Cell
            title={t('about_last_pulse')}
            value={
              sys.last_pulse === undefined || sys.last_pulse < 0
                ? t('never')
                : t('ago_sec', sys.last_pulse)
            }
          />
          <Cell
            title={t('about_pending')}
            value={sys.pending === undefined ? '—' : String(sys.pending)}
          />
        </CellGroup>
        <View className={styles.section}>
          <Text className={styles.muted}>ID: {devId}</Text>
          <Text className={styles.muted}>{t('about_hint')}</Text>
        </View>
      </View>
    </View>
  );
}
