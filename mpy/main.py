# main.py — загрузчик приложения контроллера (стабильная часть, обновляется редко).
#
# Код приложения лежит в /app (его обновляет OTA). Здесь:
#   1. применить обновление: /app_new → /app, старое → /app_prev;
#   2. считать неудачные старты: три подряд без «боевого» подтверждения
#      (app.py удаляет /ota/boots, побыв минуту онлайн) → откат на /app_prev;
#   3. запустить app.run(); любое исключение — в лог и перезагрузка через 10 с.
import os
import sys
import time

BOOTS = "/ota/boots"
MAX_BAD_BOOTS = 3


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _rmtree(path):
    try:
        for name, kind, *_ in os.ilistdir(path):
            full = path + "/" + name
            if kind & 0x4000:
                _rmtree(full)
            else:
                os.remove(full)
        os.rmdir(path)
    except OSError:
        pass


def _apply_update():
    if not _exists("/app_new"):
        return
    print("main: применяю обновление /app_new")
    _rmtree("/app_prev")
    if _exists("/app"):
        os.rename("/app", "/app_prev")
    os.rename("/app_new", "/app")


def _count_boot():
    n = 0
    try:
        with open(BOOTS) as f:
            n = int(f.read() or 0)
    except (OSError, ValueError):
        pass
    n += 1
    try:
        os.mkdir("/ota")
    except OSError:
        pass
    with open(BOOTS, "w") as f:
        f.write(str(n))
    return n


def _rollback():
    if not _exists("/app_prev"):
        return False
    print("main: новая версия не стартует — откат на /app_prev")
    _rmtree("/app_bad")
    os.rename("/app", "/app_bad")
    os.rename("/app_prev", "/app")
    _rmtree("/app_bad")
    try:
        os.remove(BOOTS)
    except OSError:
        pass
    return True


_apply_update()
if _count_boot() > MAX_BAD_BOOTS and _rollback():
    import machine
    machine.reset()

sys.path.insert(0, "/app")
try:
    import app
    app.run()
except Exception as e:
    sys.print_exception(e)
    print("main: перезагрузка через 10 с")
    time.sleep(10)
    import machine
    machine.reset()
