# Замороженные модули: стандартные для ESP32 + вся прошивка контроллера.
# Байткод лежит во флеше, а не в ОЗУ — на ESP32 без PSRAM это ~50 КБ кучи.
freeze("$(PORT_DIR)/modules")
require("ssl")        # TLS к облаку (в 1.26 ssl — модуль micropython-lib поверх tls)
require("ntptime")

# Прошивка контроллера: mpy/lib (логика, облако, железо) и загрузчик main.py.
freeze("$(BOARD_DIR)/../../../mpy/lib")
freeze("$(BOARD_DIR)/../../../mpy", ("boot.py", "main.py"))
