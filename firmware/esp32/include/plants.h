// plants.h 🌿 Справочник растений: имя → порог влажности, %.
//
// Файл /plants.ini на SD (или во флеше, если карты нет), строки «Томаты=60».
// При первом запуске создаётся со стандартной таблицей; правится вручную или из панели.
// В облако уходит постранично (DP plants, ≤ 255 байт): «стр/всего|Имя=60;Имя=65».
// Команды из панели (DP plant_cmd): «list:N», «add:Имя=60», «del:Имя».
#pragma once
#include <Arduino.h>
#include <FS.h>
#include <vector>

class Plants {
 public:
  static constexpr const char* PATH = "/plants.ini";
  static constexpr size_t PAGE_BYTES = 240;   // запас до лимита строки DP Tuya (255)

  void begin(fs::FS& fs);                 // прочитать файл, при отсутствии — записать стандартный
  bool command(const String& cmd);        // list/add/del; false — непонятная команда
  const String& page() const { return _page; }
  size_t size() const { return _items.size(); }
  int border(const String& name) const;  // -1, если нет

 private:
  struct Item {
    String name;
    uint8_t border;
  };
  fs::FS* _fs = nullptr;
  std::vector<Item> _items;
  String _page;
  int _pageNo = 0;

  void loadDefaults();
  bool save();
  void parse(const String& text);
  void buildPage();
  static String clean(const String& name);
};
