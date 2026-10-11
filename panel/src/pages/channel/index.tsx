// Экран грядки: влажность и состояние клапана, режим, порог, имя, калибровка датчика.
import React, { useEffect, useState } from 'react';
import { View, Text, useQuery, navigateTo, navigateBack } from '@ray-js/ray';
import { NavBar, Slider, Cell, CellGroup, Field, Dialog, Popup, DateTimePicker } from '@ray-js/smart-ui';
import { useActions, useDevice, useProps } from '@ray-js/panel-sdk';
import { Ch, MODES, t, bedName, parseAdcRaw } from '@/lib/dp';
import { useChannel, useBedNames } from '@/lib/hooks';
import { loadDailyFromLog, loadHourlyFromLog, loadValveDay, dayOf } from '@/lib/cloud';
import Chart from '@/components/Chart';
import ValveChart from '@/components/ValveChart';
import chartStyles from '@/components/chart.module.less';
import styles from '@/components/common.module.less';
import page from '../home/index.module.less';

const MAX_BACK = 90; // на сколько дней назад можно выбрать день

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
  // график: по часам за выбранный день (0 — сегодня, 1 — вчера, … MAX_BACK; день из календаря) или по дням за неделю/месяц
  const [dayBack, setDayBack] = useState(0);
  const [range, setRange] = useState<'day' | 'week' | 'month'>('day');
  const week = range !== 'day';
  const [hourly, setHourly] = useState<(number | null)[]>([]);
  const [daily, setDaily] = useState<{ day: string; value: number }[]>([]);
  const [loading, setLoading] = useState(false);
  const [valveDay, setValveDay] = useState<{ intervals: [number, number][]; end: number } | null>(null);

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
      Promise.all([
        loadHourlyFromLog(devId, 130 + ch, dayOf(dayBack)).then(setHourly),
        loadValveDay(devId, 140 + ch, dayOf(dayBack)).then(setValveDay),
      ]).then(done, done);
  }, [devId, ch, dayBack, range]);

  const dayTitle = (back: number) => {
    if (back === 0) return t('today');
    if (back === 1) return t('yesterday');
    const d = dayOf(back);
    return `${d.slice(6)}.${d.slice(4, 6)}.${d.slice(0, 4)}`;
  };
  // календарь: свой (smart-ui), подписи из i18n — системный Picker показывал китайский
  const [picking, setPicking] = useState(false);
  const midnight = (ts: number) => {
    const d = new Date(ts);
    return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  };
  const pickDay = (ts: number) => {
    const diff = Math.round((midnight(Date.now()) - midnight(ts)) / 86400000);
    setDayBack(Math.min(MAX_BACK, Math.max(0, diff)));
    setPicking(false);
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
          <Text className={styles.sectionTitle}>{t('humidity_chart')}</Text>
          <View className={`${styles.segment} ${chartStyles.seg3}`}>
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
          {!week && (
            <View className={`${styles.row} ${chartStyles.dayRow}`}>
              <Text className={styles.navBtn} onClick={() => setDayBack(Math.min(MAX_BACK, dayBack + 1))}>
                {'<'}
              </Text>
              <Text className={chartStyles.datePick} onClick={() => setPicking(true)}>
                📅 {dayTitle(dayBack)}
              </Text>
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
              line={range === 'month'}
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
              labelEvery={4}
              line
            />
          )}
          {!loading && !week && valveDay && (
            <View>
              <Text className={styles.sectionTitle}>{t('valve_chart')}</Text>
              <ValveChart intervals={valveDay.intervals} end={valveDay.end} />
            </View>
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
      <Popup show={picking} position="bottom" round onClose={() => setPicking(false)}>
        <DateTimePicker
          type="date"
          value={midnight(Date.now() - dayBack * 86400000)}
          minDate={midnight(Date.now() - MAX_BACK * 86400000)}
          maxDate={Date.now()}
          title={t('pick_day')}
          confirmButtonText={t('confirm_yes')}
          cancelButtonText={t('cancel')}
          locale={{ year: '', month: '', day: '' }}
          columnsOrder={[2, 1, 0]}
          onConfirm={(e: any) => pickDay(Number(e.detail))}
          onCancel={() => setPicking(false)}
        />
      </Popup>
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
