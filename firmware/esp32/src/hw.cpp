// hw.cpp 🔌 Железо: PCF8574 (клапаны), реле, мультиплексор + АЦП, расходомер, кнопка, светодиод
#include "hw.h"
#include "log.h"

// 💧 счётчики расходомера — пишутся из прерывания
static volatile uint32_t s_pulses = 0;
static volatile uint32_t s_lastPulseMs = 0;
static volatile uint32_t s_lastGapMs = 0;

void IRAM_ATTR Hardware::onPulse() {
  uint32_t now = millis();
  if (s_lastPulseMs != 0) s_lastGapMs = now - s_lastPulseMs;
  s_lastPulseMs = now;
  s_pulses++;
}

void Hardware::begin() {
  // 🛑 сначала реле в «выключено»: до инициализации входы релейных модулей висели бы в воздухе
  pinMode(pins::PUMP, OUTPUT);  digitalWrite(pins::PUMP, LOW);
  pinMode(pins::DRAIN, OUTPUT); digitalWrite(pins::DRAIN, LOW);
  pinMode(pins::FILL, OUTPUT);  digitalWrite(pins::FILL, LOW);
  pinMode(pins::LED, OUTPUT);   digitalWrite(pins::LED, LOW);
  pinMode(pins::BUTTON, INPUT_PULLDOWN);   // нажата = HIGH; без подтяжки вход плавал
  pinMode(pins::LIGHT, INPUT_PULLDOWN);    // оборван кабель → «день»
  pinMode(pins::RAIN, INPUT_PULLUP);       // оборван кабель → «сухо»
  for (uint8_t p : pins::MUX) { pinMode(p, OUTPUT); digitalWrite(p, LOW); }
  pinMode(pins::ADC_IN, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(pins::ADC_IN, ADC_11db);   // 0..3.3 В → 0..4095

  Wire.begin(pins::SDA, pins::SCL, 100000);
  // 🚰 PCF8574: три попытки, без платы продолжаем (авария «клапаны»)
  for (int attempt = 1; attempt <= 3 && !_pcfOk; attempt++) {
    if (writePcf()) break;
    LOG_E("PCF8574 не отвечает (попытка %d из 3)", attempt);
    delay(300);
  }
  if (_pcfOk) LOG_I("Клапаны (PCF8574) инициализированы");

  pinMode(pins::FLOW, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(pins::FLOW), onPulse, FALLING);
}

// 📤 Байт PCF8574: бит = 1 → клапан закрыт (реле активны LOW)
bool Hardware::writePcf() {
  uint8_t b = 0xFF;
  for (uint8_t i = 0; i < N; i++) if (_open[i]) b &= ~(1 << i);
  Wire.beginTransmission(pins::PCF_ADDR);
  Wire.write(b);
  bool ok = Wire.endTransmission() == 0;
  if (ok != _pcfOk) {
    _pcfOk = ok;
    if (ok) LOG_I("PCF8574 снова отвечает"); else LOG_E("PCF8574: ошибка записи");
  }
  return ok;
}

void Hardware::setValve(uint8_t i, bool open) {
  if (i >= N || _open[i] == open) return;
  _open[i] = open;
  writePcf();
}

uint8_t Hardware::countOpen() const {
  uint8_t n = 0;
  for (bool o : _open) if (o) n++;
  return n;
}

void Hardware::setPump(bool on) { _pump = on; digitalWrite(pins::PUMP, on ? HIGH : LOW); }
void Hardware::setDrain(bool on) { _drain = on; digitalWrite(pins::DRAIN, on ? HIGH : LOW); }
void Hardware::setFill(bool on) { _fill = on; digitalWrite(pins::FILL, on ? HIGH : LOW); }

void Hardware::allOff() {
  for (uint8_t i = 0; i < N; i++) _open[i] = false;
  writePcf();            // пишем всегда, даже если плата помечена неисправной — попытка стоит миллисекунды
  setPump(false);
  setDrain(false);
  setFill(false);
}

int Hardware::adc(uint8_t ch) {
  for (uint8_t j = 0; j < 3; j++) digitalWrite(pins::MUX[j], (ch >> j) & 1);
  delay(20);                       // установление сигнала после переключения мультиплексора
  int s[9];
  for (int k = 0; k < 9; k++) { s[k] = analogRead(pins::ADC_IN); delayMicroseconds(200); }
  for (int i = 1; i < 9; i++) {    // сортировка вставками → медиана
    int v = s[i], j = i - 1;
    while (j >= 0 && s[j] > v) { s[j + 1] = s[j]; j--; }
    s[j + 1] = v;
  }
  _lastRaw[ch] = s[4];
  return s[4];
}

bool Hardware::sensorsOk() const {
  for (int v : _lastRaw) if (v > 20 && v < 4075) return true;
  return false;
}

uint32_t Hardware::takePulses() {
  uint32_t total = s_pulses;
  uint32_t d = total - _taken;
  _taken = total;
  return d;
}

uint32_t Hardware::totalPulses() const { return s_pulses; }

float Hardware::flowLpm() const {
  uint32_t last = s_lastPulseMs, gap = s_lastGapMs;
  if (last == 0 || gap == 0) return 0;
  uint32_t silence = millis() - last;
  if (silence > 5000 && silence > gap * 2) return 0;   // поток встал
  return 60000.0f / (gap * PULSES_PER_LITER);
}

uint32_t Hardware::msSinceLastPulse() const {
  uint32_t last = s_lastPulseMs;
  return last == 0 ? 0xFFFFFFFFUL : millis() - last;
}
