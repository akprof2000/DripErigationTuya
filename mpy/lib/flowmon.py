"""flowmon.py — контроль засора фильтра по расходомеру (порт objects.cpp, fm*).

Модель: ожидаемый поток = эталон_на_клапан × открытых клапанов (+ добавка
дренажа, если идёт пролив). Эталоны набираются сами на чистом фильтре
(авто-максимум с защитой от разовых всплесков) и сбрасываются командой
«фильтр прочищен». Засор — измеренный поток ниже clog_threshold % от
ожидаемого в FM_BAD_WINDOWS окнах подряд.

Окно замера начинается не сразу после открытия клапана: пустая труба
наполняется, поток кратковременно завышен. Ждём, пока скорость перестанет
падать между соседними подынтервалами (но не раньше SETTLE_MIN и не дольше
SETTLE_CAP), и только потом меряем окнами по WINDOW секунд. Окно, в котором
работал пусковой насос, для оценки фильтра не годится (поток завышен).

Всё время — в секундах монотонных часов устройства (now из Device.tick),
расход — по общему счётчику импульсов расходомера.
"""
PULSES_PER_LITER = 450

SETTLE_MIN = 600          # с — раньше стабилизация не засчитывается (FM_SETTLE_MIN_MS)
SUBSAMPLE = 60            # с — подынтервал при ожидании стабилизации
SETTLE_STABLE_PCT = 10    # поток упал меньше чем на N % к прошлому подынтервалу → стабилен
STABLE_NEEDED = 2         # стабильных подынтервалов подряд
SETTLE_CAP = 900          # с — потолок ожидания, дальше меряем принудительно
WINDOW = 120              # с — окно замера скорости
MIN_PULSES = 10           # меньше импульсов в окне — поток незначим (пустой бак?)
BAD_WINDOWS = 3           # «плохих» окон подряд для тревоги
ALERT_REPEAT = 86400      # с — повтор тревоги не чаще раза в сутки
SPIKE_CONFIRM = 300       # с — подтверждение повышенного эталона
SPIKE_TOLERANCE_L = 1.0   # л/мин — допустимый откат от минимума кандидата


def rate_of(pulses, sec):
    """л/мин по числу импульсов за sec секунд."""
    if sec <= 0:
        return 0.0
    return pulses / PULSES_PER_LITER * 60.0 / sec


class FlowMonitor:
    def __init__(self, cfg):
        self.cfg = cfg                 # clean_flow_per_valve, clean_flow_drain, clog_threshold, flow_monitor
        self.rate = 0.0                # последняя измеренная скорость, л/мин
        self.alert = False             # тревога засора активна
        self.dirty = False             # эталон изменился — пора сохранить настройки
        self._reset_window()
        self.bad_windows = 0
        self.last_alert_at = None

    def _reset_window(self):
        self.count = 0                 # клапанов в текущей конфигурации (0 = не мониторим)
        self.draining = False
        self.measuring = False
        self.boost_tainted = False
        self.phase_start = 0.0
        self.measure_start = 0.0
        self.measure_pulses = 0
        self.sub_start = 0.0
        self.sub_pulses = 0
        self.prev_sub_rate = -1.0
        self.stable_count = 0
        self.candidate = -1.0          # кандидат на эталон (минимум за время всплеска)
        self.candidate_at = 0.0

    def recalibrate(self):
        """«Фильтр прочищен»: эталоны заново, тревога снята."""
        self.cfg.clean_flow_per_valve = 0.0
        self.cfg.clean_flow_drain = 0.0
        self.alert = False
        self.bad_windows = 0
        self.candidate = -1.0
        self.dirty = True

    def tick(self, now, pulses, count, draining, boost, filling):
        """Вызывать каждую секунду. → список событий: [("clog", rate, expected)] | [("clog_end",)] | []."""
        if not self.cfg.flow_monitor:
            self.count = 0
            self.measuring = False
            return []
        if count == 0 or filling:
            self.count = 0
            self.measuring = False
            return []

        # 🔄 сменилась конфигурация — труба наполняется заново, всё с начала
        if count != self.count or draining != self.draining:
            self._reset_window()
            self.count, self.draining = count, draining
            self.phase_start = self.sub_start = now
            self.boost_tainted = boost
            self.sub_pulses = pulses
            return []

        if not self.measuring:
            if boost:
                self.boost_tainted = True
            if now - self.phase_start >= SETTLE_CAP:
                self._start_measure(now, pulses, boost)
                return []
            if now - self.sub_start < SUBSAMPLE:
                return []
            sub_rate = rate_of(pulses - self.sub_pulses, now - self.sub_start)
            self.rate = sub_rate
            past_min = now - self.phase_start >= SETTLE_MIN
            if past_min and self.prev_sub_rate >= 0.0:
                still_falling = sub_rate < self.prev_sub_rate * (1.0 - SETTLE_STABLE_PCT / 100.0)
                self.stable_count = 0 if still_falling else self.stable_count + 1
            else:
                self.stable_count = 0
            self.prev_sub_rate = sub_rate
            self.sub_start, self.sub_pulses = now, pulses
            if past_min and self.stable_count >= STABLE_NEEDED:
                self._start_measure(now, pulses, boost)
            return []

        if boost:
            self.boost_tainted = True
        if now - self.measure_start < WINDOW:
            return []
        d_pulses = pulses - self.measure_pulses
        d_sec = now - self.measure_start
        self.measure_start, self.measure_pulses = now, pulses
        tainted = self.boost_tainted
        self.boost_tainted = boost
        self.rate = rate_of(d_pulses, d_sec)
        if d_pulses < MIN_PULSES:
            return []                  # почти нет потока: пустой бак / сухой ход, не засор
        if tainted:
            return []                  # окно с пусковым насосом — поток завышен
        return self._process(now, count, draining, self.rate)

    def _start_measure(self, now, pulses, boost):
        self.measuring = True
        self.measure_start, self.measure_pulses = now, pulses
        self.boost_tainted = boost

    def _process(self, now, cnt, draining, rate):
        cfg = self.cfg
        per_valve = cfg.clean_flow_per_valve
        if not draining:
            measured = rate / cnt
            if measured <= per_valve:
                self.candidate = -1.0
            else:
                rollback = self.candidate >= 0.0 and measured < self.candidate - SPIKE_TOLERANCE_L
                if self.candidate < 0.0 or rollback:
                    self.candidate, self.candidate_at = measured, now
                elif measured < self.candidate:
                    self.candidate = measured          # минимум за время всплеска
                if now - self.candidate_at >= SPIKE_CONFIRM:
                    cfg.clean_flow_per_valve = self.candidate
                    self.dirty = True
                    self.bad_windows = 0
                    self.candidate = -1.0
                return []                              # поток выше эталона — засора нет
        elif per_valve > 0.0:
            extra = max(0.0, rate - per_valve * cnt)
            if extra > cfg.clean_flow_drain:
                cfg.clean_flow_drain = extra
                self.dirty = True
                self.bad_windows = 0
                return []

        if per_valve <= 0.0 or (draining and cfg.clean_flow_drain <= 0.0):
            return []                                  # эталон ещё не набран
        expected = per_valve * cnt + (cfg.clean_flow_drain if draining else 0.0)
        if expected <= 0.0:
            return []
        ratio = rate / expected * 100.0
        if ratio < cfg.clog_threshold:
            self.bad_windows = min(255, self.bad_windows + 1)
            if self.bad_windows >= BAD_WINDOWS:
                if not self.alert or now - self.last_alert_at > ALERT_REPEAT:
                    self.alert = True
                    self.last_alert_at = now
                    return [("clog", rate, expected)]
            return []
        self.bad_windows = 0
        if self.alert:
            self.alert = False
            return [("clog_end", rate)]
        return []
