# boot.py — выполняется до main.py. Только то, что должно быть всегда:
# отключить отладочный вывод Wi-Fi-стека и дать сборщику мусора порог.
import gc

try:
    import esp
    esp.osdebug(None)
except ImportError:
    pass

gc.threshold(32 * 1024)
