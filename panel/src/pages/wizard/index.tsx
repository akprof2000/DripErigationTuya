// Мастер: калибровка датчика (calib), поиск датчика (search), ручной ввод мин/макс (manual).
// Протокол: команда JSON в DP wizard, ответ JSON в DP wizard_state (docs/dp.md).
import React, { useEffect, useRef, useState } from 'react';
import { View, Text, useQuery, navigateBack } from '@ray-js/ray';
import { NavBar, Button, Field } from '@ray-js/smart-ui';
import { useActions, useProps } from '@ray-js/panel-sdk';
import { t, parseAdcRaw } from '@/lib/dp';
import styles from '@/components/common.module.less';
import page from '../home/index.module.less';

type WizardState = {
  op: string;
  step?: 'wet' | 'dry' | 'finish' | 'done';
  ch?: number;
  ok?: boolean;
  err?: string;
  wet?: number;
  dry?: number;
  min?: number;
  max?: number;
  found?: number;
};

const STEPS = ['wet', 'dry', 'finish'] as const;

function parseState(raw: string | undefined): WizardState {
  try {
    return raw ? JSON.parse(raw) : { op: 'idle' };
  } catch {
    return { op: 'idle' };
  }
}

export default function WizardPage() {
  const query = useQuery<{ op?: string; ch?: string }>();
  const op = query.op === 'search' || query.op === 'manual' ? query.op : 'calib';
  const ch = Number(query.ch) || 1;
  const actions = useActions();
  const state = parseState(useProps(p => p.wizard_state as string));
  const adc = parseAdcRaw(useProps(p => p.adc_raw as string))[ch - 1];
  const [waiting, setWaiting] = useState(op !== 'manual');
  const [min, setMin] = useState('');
  const [max, setMax] = useState('');
  const lastRaw = useRef('');

  const send = (cmd: Record<string, unknown>) => {
    setWaiting(true);
    actions.wizard.set(JSON.stringify(cmd));
  };

  // старт мастера при открытии; при уходе со страницы незавершённый мастер отменяем
  useEffect(() => {
    if (op === 'calib') send({ op: 'calib', ch, step: 'start' });
    if (op === 'search') send({ op: 'search', step: 'start' });
    return () => {
      const s = parseState(lastRaw.current);
      if (s.op === op && s.step && s.step !== 'done')
        actions.wizard.set(JSON.stringify({ op, step: 'cancel' }));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const raw = JSON.stringify(state);
  useEffect(() => {
    lastRaw.current = raw;
    setWaiting(false);
  }, [raw]);

  const mine = state.op === op;
  const step = mine ? state.step : undefined;
  const title = op === 'search' ? t('wz_search_title') : t('wz_calib_title', ch);

  const resultText = () => {
    if (state.ok) {
      if (op === 'calib') return t('wz_ok_calib', state.min ?? 0, state.max ?? 0);
      if (op === 'manual') return t('wz_ok_manual', state.min ?? 0, state.max ?? 0);
      return t('wz_ok_search', state.found ?? 0);
    }
    const key = `wz_err_${state.err}`;
    const text = t(key);
    return text && text !== key ? text : t('wz_err_other', state.err ?? '?');
  };

  return (
    <View className={page.page}>
      <NavBar title={title} leftArrow onClickLeft={() => navigateBack()} />
      <View className={page.body}>
        <View className={styles.section}>
          {op !== 'manual' && (
            <View className={styles.steps}>
              {STEPS.slice(0, op === 'search' ? 2 : 3).map((s, i) => (
                <View
                  key={s}
                  className={`${styles.stepBar} ${
                    step === 'done' || STEPS.indexOf(step as never) >= i ? styles.stepDone : ''
                  }`}
                />
              ))}
            </View>
          )}

          {op === 'manual' && step !== 'done' && (
            <View>
              <Field
                label={t('adc_wet')}
                type="number"
                value={min}
                onChange={(e: any) => setMin(String(e.detail))}
              />
              <Field
                label={t('adc_dry')}
                type="number"
                value={max}
                onChange={(e: any) => setMax(String(e.detail))}
              />
              {adc && (
                <Text className={styles.muted}>
                  {t('adc_now')} {adc.cur}
                </Text>
              )}
            </View>
          )}

          {step && step !== 'done' && op !== 'manual' && (
            <View>
              <Text className={`${styles.big} ${styles.center}`}>{t(`wz_${op}_${step}`)}</Text>
              <Text className={`${styles.muted} ${styles.center}`}>
                {t(`wz_${op}_${step}_hint`)}
              </Text>
              {op === 'calib' && adc && (
                <Text className={`${styles.muted} ${styles.center}`}>
                  {t('adc_now')} {adc.cur}
                  {state.wet !== undefined ? ` · ${t('adc_wet')} ${state.wet}` : ''}
                </Text>
              )}
            </View>
          )}

          {mine && step === 'done' && (
            <Text className={`${styles.big} ${styles.center}`}>{resultText()}</Text>
          )}
          {waiting && <Text className={`${styles.muted} ${styles.center}`}>{t('wz_waiting')}</Text>}
          {mine && state.err === 'bad_step' && (
            <Text className={styles.muted}>{t('wz_err_bad_step')}</Text>
          )}
        </View>

        <View className={styles.buttons}>
          {step === 'done' ? (
            <Button block type="primary" onClick={() => navigateBack()}>
              {t('close')}
            </Button>
          ) : op === 'manual' ? (
            <Button
              block
              type="primary"
              onClick={() =>
                send({ op: 'manual', ch, min: Number(min) || 0, max: Number(max) || 0 })
              }
            >
              {t('save')}
            </Button>
          ) : (
            <>
              <Button block plain onClick={() => send({ op, step: 'cancel' })}>
                {t('cancel')}
              </Button>
              <Button
                block
                type="primary"
                disabled={waiting || !step}
                onClick={() => send({ op, step: step === 'finish' ? 'finish' : 'next' })}
              >
                {step === 'finish' ? t('finish') : t('next')}
              </Button>
            </>
          )}
        </View>
      </View>
    </View>
  );
}
