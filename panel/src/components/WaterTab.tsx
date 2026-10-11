// Вкладка «Вода»: расход сейчас/за полив/всего, расход по дням, состояние фильтра.
import React, { useEffect, useState } from 'react';
import { View, Text } from '@ray-js/ray';
import { Button, Dialog, DialogInstance } from '@ray-js/smart-ui';
import { useActions, useDevice, useProps } from '@ray-js/panel-sdk';
import { t, faultsOf } from '@/lib/dp';
import { useStatus } from '@/lib/hooks';
import { loadDailyFromLog } from '@/lib/cloud';
import Chart from './Chart';
import PeriodNav from './PeriodNav';
import chartStyles from './chart.module.less';
import styles from './common.module.less';

const FLOW_TOTAL_DP = 108;

export default function WaterTab() {
  const s = useStatus();
  const actions = useActions();
  const devId = useDevice(d => d.devInfo?.devId);
  const clogThreshold = useProps(p => p.clog_threshold as number) ?? 50;
  const monitor = useProps(p => p.flow_monitor as boolean);
  const clogged = faultsOf(s.fault).includes('filter_clog');
  const [daily, setDaily] = useState<{ day: string; value: number }[]>([]);
  const [month, setMonth] = useState(false);
  const [back, setBack] = useState(0);

  useEffect(() => {
    // flow_total — накопительный счётчик (scale 1): прирост за сутки = расход за день, л
    if (devId)
      loadDailyFromLog(devId, FLOW_TOTAL_DP, month ? 30 : 7, 'delta', 1, back).then(setDaily);
  }, [devId, month, back]);

  const maxDay = Math.max(1, ...daily.map(d => d.value));
  const confirm = (message: string, run: () => void) =>
    DialogInstance.confirm({
      message,
      cancelButtonText: t('cancel'),
      confirmButtonText: t('confirm_yes'),
    })
      .then(run)
      .catch(() => undefined);

  return (
    <View>
      <View className={styles.stats}>
        <View className={styles.card}>
          <Text className={styles.muted}>{t('water_now')}</Text>
          <Text className={styles.big}>{s.flowRate.toFixed(2)}</Text>
          <Text className={styles.muted}>{t('lpm')}</Text>
        </View>
        <View className={styles.card}>
          <Text className={styles.muted}>{t('water_session')}</Text>
          <Text className={styles.big}>{s.flowSession.toFixed(1)}</Text>
          <Text className={styles.muted}>{t('liters')}</Text>
        </View>
        <View className={styles.card}>
          <Text className={styles.muted}>{t('water_total')}</Text>
          <Text className={styles.big}>{Math.round(s.flowTotal)}</Text>
          <Text className={styles.muted}>{t('liters')}</Text>
        </View>
      </View>

      <View className={styles.section}>
        <Text className={styles.sectionTitle}>{t('water_by_day')}</Text>
        <View
          className={`${styles.segment} ${chartStyles.segGap}`}
          style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}
        >
          {[false, true].map(m => (
            <Text
              key={String(m)}
              className={`${styles.segItem} ${month === m ? styles.segActive : ''}`}
              onClick={() => setMonth(m)}
            >
              {t(m ? 'by_month' : 'by_week')}
            </Text>
          ))}
        </View>
        <PeriodNav back={back} span={month ? 30 : 7} onChange={setBack} />
        {daily.some(d => d.value > 0) ? (
          <Chart
            points={daily.map(d => ({
              label: `${d.day.slice(6)}.${d.day.slice(4, 6)}`,
              value: d.value,
            }))}
            unit={t('liters')}
            showValues={!month}
            labelEvery={month ? 5 : 1}
          />
        ) : (
          <Text className={styles.muted}>{t('water_no_chart')}</Text>
        )}
        {s.sys.pulses !== undefined && (
          <Text className={styles.muted}>
            {t(
              'flow_diag',
              s.sys.pulses,
              s.sys.last_pulse === undefined || s.sys.last_pulse < 0
                ? t('never')
                : t('ago_sec', s.sys.last_pulse)
            )}
          </Text>
        )}
      </View>

      <View className={`${styles.section} ${clogged ? styles.warnBox : ''}`}>
        <View className={styles.row}>
          <Text className={styles.sectionTitle}>{t('filter')}</Text>
          <Text className={`${styles.chip} ${clogged ? styles.chip_warn : styles.chip_ok}`}>
            {monitor === false ? t('filter_off') : clogged ? t('filter_clog') : t('filter_ok')}
          </Text>
        </View>
        <Text className={styles.muted}>
          {s.filterBaseline > 0
            ? t('filter_line', s.filterBaseline.toFixed(3), clogThreshold)
            : t('filter_learning')}
        </Text>
        <View className={styles.buttons}>
          <Button
            block
            onClick={() =>
              confirm(t('confirm_filter_cleaned'), () => actions.command.set('filter_cleaned'))
            }
          >
            {t('filter_cleaned')}
          </Button>
        </View>
      </View>

      <View className={styles.buttons}>
        <Button
          block
          plain
          disabled={s.drain}
          onClick={() => confirm(t('confirm_drain'), () => actions.command.set('drain'))}
        >
          {s.drain ? t('drain_running') : t('drain_now')}
        </Button>
        <Button
          block
          plain
          onClick={() => confirm(t('confirm_clear_flow'), () => actions.command.set('clear_flow'))}
        >
          {t('clear_flow')}
        </Button>
      </View>
      <Dialog id="smart-dialog" />
    </View>
  );
}
