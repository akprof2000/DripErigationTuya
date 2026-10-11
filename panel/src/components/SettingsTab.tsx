// Вкладка «Настройки»: всё из Config прошивки + режим всех грядок + команды.
import React from 'react';
import { View, Text, navigateTo, reLaunch } from '@ray-js/ray';
import { Button, Cell, CellGroup, Dialog, DialogInstance, Stepper, Switch } from '@ray-js/smart-ui';
import { useActions, useProps } from '@ray-js/panel-sdk';
import { MODES, t } from '@/lib/dp';
import { LANGS, Lang, currentLang, setLang } from '@/i18n';
import styles from './common.module.less';

type BoolCode = 'run_on_rain' | 'run_on_night' | 'flow_monitor' | 'autocal_no_delay';
type NumCode = 'delta_hum' | 'delta_calib' | 'boost_pump_valves' | 'clog_threshold';

export default function SettingsTab() {
  const p = useProps();
  const actions = useActions();

  const toggle = (code: BoolCode) => (
    <Switch size="24px" checked={!!p[code]} onChange={(e: any) => actions[code].set(!!e.detail)} />
  );
  const stepper = (code: NumCode, min: number, max: number) => (
    <Stepper
      value={(p[code] as number) ?? min}
      min={min}
      max={max}
      integer
      onChange={(e: any) => actions[code].set(Number(e.detail))}
    />
  );
  const confirm = (message: string, run: () => void) =>
    DialogInstance.confirm({ message, cancelButtonText: t('cancel'), confirmButtonText: t('confirm_yes') })
      .then(run)
      .catch(() => undefined);

  const boost = (p.boost_pump_valves as number) ?? 9;
  const lang = currentLang();
  const chooseLang = (l: Lang) => {
    setLang(l);
    reLaunch({ url: '/pages/home/index' });   // строки читаются при отрисовке — перезапускаем панель
  };

  return (
    <View>
      <CellGroup inset title=" ">
        <Cell title={t('s_run_on_rain')} slot={{ rightIcon: toggle('run_on_rain') }} />
        <Cell title={t('s_run_on_night')} slot={{ rightIcon: toggle('run_on_night') }} />
        <Cell title={t('s_flow_monitor')} slot={{ rightIcon: toggle('flow_monitor') }} />
        <Cell title={t('s_autocal_no_delay')} slot={{ rightIcon: toggle('autocal_no_delay') }} />
      </CellGroup>

      <CellGroup inset title=" ">
        <Cell title={`${t('s_delta_hum')}, ±%`} slot={{ rightIcon: stepper('delta_hum', 0, 50) }} />
        <Cell title={t('s_delta_calib')} slot={{ rightIcon: stepper('delta_calib', 0, 500) }} />
        <Cell
          title={t('s_boost_pump')}
          label={boost >= 9 ? t('s_boost_off') : t('s_boost_from', boost)}
          slot={{ rightIcon: stepper('boost_pump_valves', 1, 9) }}
        />
        <Cell
          title={`${t('s_clog_threshold')}, %`}
          slot={{ rightIcon: stepper('clog_threshold', 10, 95) }}
        />
      </CellGroup>

      <View className={styles.section}>
        <Text className={styles.sectionTitle}>{t('mode_all')}</Text>
        <View className={styles.segment}>
          {MODES.map(m => (
            <Text key={m} className={styles.segItem} onClick={() => actions.mode_all.set(m)}>
              {t(`mode_${m}`)}
            </Text>
          ))}
        </View>
      </View>

      <View className={styles.section}>
        <Text className={styles.sectionTitle}>{t('s_language')}</Text>
        <View className={styles.segment}>
          {LANGS.map(l => (
            <Text
              key={l}
              className={`${styles.segItem} ${l === lang ? styles.segActive : ''}`}
              onClick={() => chooseLang(l)}
            >
              {t(`lang_${l}`)}
            </Text>
          ))}
        </View>
      </View>

      <CellGroup inset title=" ">
        <Cell
          title={t('find_sensor')}
          isLink
          onClick={() => navigateTo({ url: '/pages/wizard/index?op=search' })}
        />
        <Cell title={t('about')} isLink onClick={() => navigateTo({ url: '/pages/about/index' })} />
      </CellGroup>

      <View className={styles.buttons}>
        <Button
          block
          plain
          onClick={() => confirm(t('confirm_restart'), () => actions.command.set('restart'))}
        >
          {t('restart')}
        </Button>
        <Button
          block
          plain
          type="danger"
          onClick={() => confirm(t('confirm_reset'), () => actions.command.set('reset_settings'))}
        >
          {t('reset_settings')}
        </Button>
      </View>
      <Dialog id="smart-dialog" />
    </View>
  );
}
