import { kit } from '@ray-js/panel-sdk';
import strings from './strings';

const { I18N } = kit;

// Язык панели — язык приложения: ru, en или zh; для остальных языков I18N
// берёт en.
const Strings = new I18N(strings);

export default Strings;
