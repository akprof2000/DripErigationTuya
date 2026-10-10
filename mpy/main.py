# main.py — запуск приложения контроллера (заморожен в прошивке вместе с mpy/lib).
#
# Обновления — целым образом прошивки на второй OTA-раздел (ota.py); откат делает
# загрузчик ESP-IDF, если новая прошивка не подтвердила себя (app.py → ota.confirm()
# после минуты онлайн) и перезагрузилась — в том числе отсюда, после исключения.
import sys
import time

sys.path.insert(0, "/app")      # разработка: файлы в /app перекрывают замороженные модули

try:
    import app
    app.run()
except Exception as e:
    sys.print_exception(e)
    print("main: перезагрузка через 10 с")
    time.sleep(10)
    import machine
    machine.reset()
