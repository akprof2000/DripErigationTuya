// log.h 📝 Логгер с уровнями: [чч:мм:сс] <уровень> сообщение. Уровень задаётся -DLOG_LEVEL в platformio.ini.
#pragma once
#include <Arduino.h>

#define LOG_LEVEL_NONE 0
#define LOG_LEVEL_ERROR 1
#define LOG_LEVEL_WARN 2
#define LOG_LEVEL_INFO 3
#define LOG_LEVEL_DEBUG 4

#ifndef LOG_LEVEL
#define LOG_LEVEL LOG_LEVEL_INFO
#endif

void logPrintf(char level, const char* fmt, ...);

#if LOG_LEVEL >= LOG_LEVEL_ERROR
#define LOG_E(...) logPrintf('E', __VA_ARGS__)
#else
#define LOG_E(...) do {} while (0)
#endif
#if LOG_LEVEL >= LOG_LEVEL_WARN
#define LOG_W(...) logPrintf('W', __VA_ARGS__)
#else
#define LOG_W(...) do {} while (0)
#endif
#if LOG_LEVEL >= LOG_LEVEL_INFO
#define LOG_I(...) logPrintf('I', __VA_ARGS__)
#else
#define LOG_I(...) do {} while (0)
#endif
#if LOG_LEVEL >= LOG_LEVEL_DEBUG
#define LOG_D(...) logPrintf('D', __VA_ARGS__)
#else
#define LOG_D(...) do {} while (0)
#endif
