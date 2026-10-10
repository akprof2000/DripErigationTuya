import { kit } from '@ray-js/panel-sdk';
import { getStorageSync, getSystemInfoSync, setStorageSync } from '@ray-js/ray';
import strings from './strings';

const { I18N } = kit;

// Язык панели: по умолчанию — язык приложения (ru / en / zh по префиксу кода:
// Smart Life отдаёт коды вида ru_RU, en_US, zh_Hans), остальные языки → en.
// В настройках можно выбрать язык вручную — выбор хранится на телефоне.
export type Lang = 'auto' | 'ru' | 'en' | 'zh';
export const LANGS: Lang[] = ['auto', 'ru', 'en', 'zh'];
const KEY = 'drip_lang';

const Strings = new I18N(strings);

export function appLang(): 'ru' | 'en' | 'zh' {
  let code = '';
  try {
    code = String(getSystemInfoSync().language || '').toLowerCase();
  } catch {
    code = '';
  }
  if (code.startsWith('ru')) return 'ru';
  if (code.startsWith('zh')) return 'zh';
  return 'en';
}

export function currentLang(): Lang {
  try {
    const r: any = getStorageSync({ key: KEY });
    const v = r && typeof r === 'object' && 'data' in r ? r.data : r;
    return LANGS.includes(v as Lang) ? (v as Lang) : 'auto';
  } catch {
    return 'auto';
  }
}

export function applyLang(l: Lang) {
  Strings.setLanguage(l === 'auto' ? appLang() : l);
}

export function setLang(l: Lang) {
  try {
    setStorageSync({ key: KEY, data: l });
  } catch {
    // хранилище недоступно — язык сменится до перезапуска панели
  }
  applyLang(l);
}

applyLang(currentLang());

export default Strings;
