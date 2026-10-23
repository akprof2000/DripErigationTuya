// hw.h 🔌 Железо контроллера (пины — как pins.h старой прошивки и плата-носитель).
//
//  мультиплексор датчиков 12/13/14 → АЦП 33; дождь 15 (замкнут на GND = дождь, pull-up);
//  свет 4 (HIGH = ночь, pull-down); заливка 17, дренаж 25, насос 26 (реле, активны HIGH);
//  расходомер 27 (прерывание по спаду, 450 имп/л); кнопка 16 (нажата = HIGH, pull-down);
//  светодиод 2; I2C 21/22: PCF8574 0x20 (клапаны, реле активны LOW), DS3231 0x68.
#pragma once
#include <Arduino.h>
#include <Wire.h>

namespace pins {
constexpr uint8_t LED = 2, BUTTON = 16, LIGHT = 4, RAIN = 15, PUMP = 17, DRAIN = 25, FILL = 26,   // J5: насос, дренаж; J7: заливка
                  FLOW = 27, ADC_IN = 33, SDA = 21, SCL = 22;
constexpr uint8_t MUX[3] = {12, 13, 14};
constexpr uint8_t PCF_ADDR = 0x20, RTC_ADDR = 0x68;
}

constexpr float PULSES_PER_LITER = 450.0f;   // YF-S201

class Hardware {
 public:
  static constexpr uint8_t N = 8;

  void begin();                       // пины в безопасное состояние, I2C, PCF8574, прерывание расходомера
  // 🚰 клапаны (PCF8574): запись всего байта при каждом изменении
  void setValve(uint8_t i, bool open);
  bool valveOpen(uint8_t i) const { return _open[i]; }
  uint8_t countOpen() const;
  void setPump(bool on);
  void setDrain(bool on);
  void setFill(bool on);
  bool pumpOn() const { return _pump; }
  bool drainOn() const { return _drain; }
  bool fillOn() const { return _fill; }
  void allOff();                      // клапаны закрыть, реле выключить (перед перезагрузкой / авария)

  bool rain() const { return digitalRead(pins::RAIN) == LOW; }
  bool night() const { return digitalRead(pins::LIGHT) == HIGH; }
  bool buttonPressed() const { return digitalRead(pins::BUTTON) == HIGH; }
  void led(bool on) { digitalWrite(pins::LED, on ? HIGH : LOW); }

  // 📟 АЦП канала: мультиплексор + 20 мс + медиана из 9 (sensors.cpp)
  int adc(uint8_t ch);
  int lastRaw(uint8_t ch) const { return _lastRaw[ch]; }
  bool sensorsOk() const;             // хоть один канал не упёрся в край шкалы

  // 💧 расходомер
  uint32_t takePulses();              // импульсов с прошлого вызова
  uint32_t totalPulses() const;       // с включения
  float flowLpm() const;              // мгновенная скорость по интервалу импульсов (0 — давно нет)
  uint32_t msSinceLastPulse() const;  // 0xFFFFFFFF — импульсов не было

  bool pcfOk() const { return _pcfOk; }
  // 🩺 блокирующие аварии: "valves", если PCF8574 не отвечает
  bool faultValves() const { return !_pcfOk; }

 private:
  bool _open[N] = {};
  bool _pump = false, _drain = false, _fill = false;
  bool _pcfOk = false;
  int _lastRaw[N] = {};
  uint32_t _taken = 0;
  bool writePcf();
  static void IRAM_ATTR onPulse();
};
