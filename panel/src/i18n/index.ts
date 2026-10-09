import { kit } from '@ray-js/panel-sdk';
import strings from './strings';

const { I18N } = kit;

// Панель всегда на русском, какой бы язык ни стоял в приложении: для неизвестного
// языка I18N берёт en, поэтому под en тоже лежат русские строки. Английские
// тексты в strings.ts оставлены на случай, если язык понадобится вернуть.
const Strings = new I18N({ en: strings.ru, ru: strings.ru });

export default Strings;
