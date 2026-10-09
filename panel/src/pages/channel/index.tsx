// Экран грядки: влажность и состояние клапана, режим, порог, имя, калибровка датчика.
import React, { useEffect, useState } from 'react';
import { View, Text, useQuery, navigateTo, navigateBack } from '@ray-js/ray';
import { NavBar, Slider, Cell, CellGroup, Field, Dialog } from '@ray-js/smart-ui';
import { useActions, useDevice, useProps } from '@ray-js/panel-sdk';
import { Ch, MODES, t, bedName, parseAdcRaw } from '@/lib/dp';
import { useChannel, useBedNames } from '@/lib/hooks';
import { loadDaily } from '@/lib/cloud';
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
  const [history, setHistory] = useState<{ day: string; value: number }[]>([]);

  useEffect(() => setDraft(border), [border]);
  useEffect(() => {
    if (devId) loadDaily(devId, 130 + ch, 7, 'avg').then(setHistory);
  }, [devId, ch]);

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
          {history.length > 0 && (
            <View className={styles.chart}>
              {history.map(d => (
                <View key={d.day} className={styles.chartBar} style={{ height: `${d.value}%` }} />
              ))}
            </View>
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
