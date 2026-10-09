# Панель Drip Irrigation 8ch (Smart MiniApp, Ray)

Сделана из официального шаблона Tuya `PublicSdmTemplate`. Экраны по макету:
вкладки «Грядки», «Вода», «События», «Настройки», экран грядки и мастер
калибровки/поиска датчика.

- `src/devices/schema.ts` генерируется из `../spec/dp.json` (`python ../tools/gen_panel_schema.py`).
- `src/lib/dp.ts` — разбор DP (масштаб, adc_raw, fault, события), `src/lib/cloud.ts` —
  названия грядок (облачные свойства устройства), журнал событий, дневная статистика.
- Тексты на русском и английском — `src/i18n/strings.ts`.

## Запуск

1. На Tuya MiniApp Developer Platform создать панельный MiniApp, привязать к PID
   `0uo7msdnt2yn1lgp` (уже создан: `tyywwyyjeyzueqb7n2`, прописан в `project.tuya.json`).
2. `npm install`, затем открыть эту папку в Tuya MiniApp IDE.
3. Plugins → Panel Tools → виртуальное устройство продукта → отладка.

Проверка без IDE: `npx ray build --target tuya` и
`npx -p typescript@5.6.3 tsc --noEmit -p .` (TypeScript 4 из шаблона не читает
свежие типы Node).

Графики (влажность и расход по дням) берут облачную статистику DP — её нужно
включить в консоли Tuya для DP 108 и 131–138.
