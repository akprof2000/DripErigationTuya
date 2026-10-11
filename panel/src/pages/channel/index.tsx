// Экран грядки: влажность и состояние клапана, режим, порог, имя, калибровка датчика.
import React, { useEffect, useState } from 'react';
import { View, Text, useQuery, navigateTo, navigateBack } from '@ray-js/ray';
import { NavBar, Slider, Cell, CellGroup, Field, Dialog } from '@ray-js/smart-ui';
import { useActions, useDevice, useProps } from '@ray-js/panel-sdk';
import { Ch, MODES, t, bedName, parseAdcRaw } from '@/lib/dp';
import { useChannel, useBedNames } from '@/lib/hooks';
import { loadDailyFromLog, loadHourlyFromLog, dayOf } from '@/lib/cloud';
import Chart from '@/components/Chart';
import styles from '@/components/common.module.less';
import page from '../home/index.module.less';

export default function ChannelPage() {
  const query = useQuery<{ ch?: string }>();
  const ch = Math.min(8, Math.max(1, Number(query.ch) || 1)) as Ch;
  const { humidity, valve, mode, border } = useChannel(ch);
  const actions = useActions();
  const devId = useDevice(d => d.devInfo?.devId);
  const adc = parseAdcRaw(useProps(p => p.adc_raw as string))[ch - 1];
  const { names, rename } = useBedNames();
  const name = bedName(names, ch);
  const [draft, setDraft] = useState(border);
  // график: по часам за выбранный день (0 — сегодня, 1 — вчера, … 6) или по дням за неделю/месяц
  const [dayBack, setDayBack] = useState(0);
  const [range, setRange] = useState<'day' | 'week' | 'month'>('day');
  const week = range !== 'day';
  const [hourly, setHourly] = useState<(number | null)[]>([]);
  const [daily, setDaily] = useState<{ day: string; value: number }[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => setDraft(border), [border]);
  useEffect(() => {
    if (!devId) return;
    setLoading(true);
    const done = () => setLoading(false);
    if (week)
      loadDailyFromLog(devId, 130 + ch, range === 'month' ? 30 : 7, 'avg')
        .then(setDaily)
        .then(done, done);
    else
      loadHourlyFromLog(devId, 130 + ch, dayOf(dayBack))
        .then(setHourly)
        .then(done, done);
  }, [devId, ch, dayBack, range]);

  const dayTitle = (back: number) => {
    if (back === 0) return t('today');
    if (back === 1) return t('yesterday');
    const d = dayOf(back);
    return `${d.slice(6)}.${d.slice(4, 6)}`;
  };

  const [editing, setEditing] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const askName = () => {
    setNameDraft(names[ch - 1] ?? '');
    setEditing(true);
  };

  return (
    <View className={page.page}>
      <NavBar title={name} leftArrow onClickLeft={() => navigateBack()} />
      <View className={page.body}>
        <View className={styles.section}>
          <Text className={styles.huge}>{humidity}%</Text>
          <Text className={`${styles.center} ${styles.muted}`}>{t(`vs_${valve ?? 'init'}`)}</Text>
        </View>

        <View className={styles.section}>
          <View className={styles.row}>
            <Text className={styles.sectionTitle}>{t('humidity_chart')}</Text>
            <View className={styles.segment}>
              {(['day', 'week', 'month'] as const).map(r => (
                <Text
                  key={r}
                  className={`${styles.segItem} ${range === r ? styles.segActive : ''}`}
                  onClick={() => setRange(r)}
                >
                  {t(`by_${r}`)}
                </Text>
              ))}
            </View>
          </View>
          {!week && (
            <View className={styles.row}>
              <Text className={styles.navBtn} onClick={() => setDayBack(Math.min(6, dayBack + 1))}>
                {'<'}
              </Text>
              <Text>{dayTitle(dayBack)}</Text>
              <Text className={styles.navBtn} onClick={() => setDayBack(Math.max(0, dayBack - 1))}>
                {'>'}
              </Text>
            </View>
          )}
          {loading && <Text className={styles.muted}>{t('loading')}</Text>}
          {!loading && week && daily.length > 0 && (
            <Chart
              points={daily.map(d => ({
                label: `${d.day.slice(6)}.${d.day.slice(4, 6)}`,
                value: Math.round(d.value),
              }))}
              max={100}
              unit="%"
              threshold={border}
              showValues={range === 'week'}
              labelEvery={range === 'month' ? 5 : 1}
            />
          )}
          {!loading && !week && hourly.some(v => v !== null) && (
            <Chart
              points={hourly.map((v, h) => ({
                label: `${h}`,
                value: v === null ? null : Math.round(v),
              }))}
              max={100}
              unit="%"
              threshold={border}
              labelEvery={3}
            />
          )}
          {!loading &&
            ((week && daily.length === 0) || (!week && !hourly.some(v => v !== null))) && (
              <Text className={styles.muted}>{t('no_data')}</Text>
            )}
        </View>

        <View className={styles.section}>
          <Text className={styles.sectionTitle}>{t('mode')}</Text>
          <View className={styles.segment}>
            {MODES.map(m => (
              <Text
                key={m}
                className={`${styles.segItem} ${m === mode ? styles.segActive : ''}`}
                onClick={() => actions[`mode_${ch}`].set(m)}
              >
                {t(`mode_${m}`)}
              </Text>
            ))}
          </View>
        </View>

        <View className={styles.section}>
          <View className={styles.row}>
            <Text className={styles.sectionTitle}>{t('threshold')}</Text>
            <Text>{draft}%</Text>
          </View>
          <Slider
            value={draft}
            min={0}
            max={100}
            step={1}
            onChange={v => setDraft(v)}
            onAfterChange={v => actions[`border_${ch}`].set(v)}
          />
        </View>

        <CellGroup inset title=" ">
          <Cell title={t('rename')} value={name} isLink onClick={askName} />
          <Cell
            title={t('calibration')}
            label={
              adc
                ? `${t('adc_now')} ${adc.cur} · ${t('adc_wet')} ${adc.min} · ${t('adc_dry')} ${
                    adc.max
                  }`
                : ''
            }
            isLink
            onClick={() => navigateTo({ url: `/pages/wizard/index?op=calib&ch=${ch}` })}
          />
          <Cell
            title={t('manual_calib')}
            isLink
            onClick={() => navigateTo({ url: `/pages/wizard/index?op=manual&ch=${ch}` })}
          />
        </CellGroup>
      </View>
      <Dialog
        show={editing}
        title={t('rename')}
        useSlot
        showCancelButton
        cancelButtonText={t('cancel')}
        confirmButtonText={t('save')}
        onConfirm={() => {
          rename(ch, nameDraft);
          setEditing(false);
        }}
        onCancel={() => setEditing(false)}
        onClose={() => setEditing(false)}
      >
        <Field
          value={nameDraft}
          placeholder={`${t('bed')} ${ch}`}
          maxlength={30}
          onChange={(e: any) => setNameDraft(String(e.detail))}
        />
      </Dialog>
    </View>
  );
}
