// plants.cpp 🌿 Справочник растений в /plants.ini
#include "plants.h"
#include "log.h"
#include "storage.h"

// 🌱 стандартная таблица: влажность почвы по датчику, ниже которой пора поливать
static const struct { const char* name; uint8_t border; } DEFAULTS[] = {
    {"Томаты", 60},   {"Огурцы", 70},   {"Кабачки", 65},  {"Баклажаны", 65},
    {"Перец", 65},    {"Клубника", 65}, {"Картофель", 60}, {"Морковь", 60},
    {"Свёкла", 60},   {"Капуста", 70},  {"Салат", 70},    {"Зелень", 70},
    {"Редис", 70},    {"Укроп", 60},    {"Петрушка", 60}, {"Лук", 55},
    {"Чеснок", 50},   {"Горох", 60},    {"Фасоль", 60},   {"Тыква", 60},
    {"Арбуз", 50},    {"Дыня", 50},     {"Малина", 60},   {"Смородина", 60},
    {"Цветы", 55},
};

void Plants::begin(fs::FS& fs) {
  _fs = &fs;
  String text = readFile(fs, PATH);
  if (text.length()) parse(text);
  if (_items.empty()) {
    loadDefaults();
    if (save()) LOG_I("plants: создан %s (%u растений)", PATH, (unsigned)_items.size());
  } else {
    LOG_I("plants: %u растений из %s", (unsigned)_items.size(), PATH);
  }
  _pageNo = 0;
  buildPage();
}

void Plants::loadDefaults() {
  _items.clear();
  for (auto& d : DEFAULTS) _items.push_back({d.name, d.border});
}

void Plants::parse(const String& text) {
  _items.clear();
  int start = 0;
  while (start < (int)text.length()) {
    int end = text.indexOf('\n', start);
    if (end < 0) end = text.length();
    String line = text.substring(start, end);
    start = end + 1;
    line.trim();
    if (!line.length() || line[0] == ';' || line[0] == '#' || line[0] == '[') continue;
    int eq = line.indexOf('=');
    if (eq <= 0) continue;
    String name = clean(line.substring(0, eq));
    int b = line.substring(eq + 1).toInt();
    if (name.length() && b >= 0 && b <= 100 && border(name) < 0) _items.push_back({name, (uint8_t)b});
  }
}

bool Plants::save() {
  if (!_fs) return false;
  String out = "; Справочник растений: имя=порог влажности почвы, %\n"
               "; ниже порога (минус delta_hum) грядка поливается\n[plants]\n";
  for (auto& it : _items) out += it.name + "=" + it.border + "\n";
  bool ok = writeFile(*_fs, PATH, out);
  if (!ok) LOG_E("plants: не записать %s", PATH);
  return ok;
}

String Plants::clean(const String& name) {
  String s = name;
  s.replace(";", " ");
  s.replace("=", " ");
  s.replace("|", " ");
  s.trim();
  return s.substring(0, 32);
}

int Plants::border(const String& name) const {
  for (auto& it : _items)
    if (it.name.equalsIgnoreCase(name)) return it.border;
  return -1;
}

// 📄 страница: «номер/всего|Имя=60;Имя=65», не длиннее PAGE_BYTES
void Plants::buildPage() {
  std::vector<String> pages;
  String cur;
  for (auto& it : _items) {
    String e = it.name + "=" + it.border;
    if (cur.length() && cur.length() + 1 + e.length() > PAGE_BYTES - 8) {
      pages.push_back(cur);
      cur = "";
    }
    if (cur.length()) cur += ";";
    cur += e;
  }
  pages.push_back(cur);
  if (_pageNo >= (int)pages.size()) _pageNo = pages.size() - 1;
  _page = String(_pageNo) + "/" + pages.size() + "|" + pages[_pageNo];
}

bool Plants::command(const String& cmd) {
  int colon = cmd.indexOf(':');
  String op = colon < 0 ? cmd : cmd.substring(0, colon);
  String arg = colon < 0 ? "" : cmd.substring(colon + 1);
  if (op == "list") {
    _pageNo = arg.toInt();
  } else if (op == "add") {
    int eq = arg.indexOf('=');
    if (eq <= 0) return false;
    String name = clean(arg.substring(0, eq));
    int b = arg.substring(eq + 1).toInt();
    if (!name.length() || b < 0 || b > 100) return false;
    bool found = false;
    for (auto& it : _items)
      if (it.name.equalsIgnoreCase(name)) { it.border = b; found = true; }
    if (!found) _items.push_back({name, (uint8_t)b});
    save();
    _pageNo = 0;
  } else if (op == "del") {
    String name = clean(arg);
    for (size_t i = 0; i < _items.size(); i++)
      if (_items[i].name.equalsIgnoreCase(name)) { _items.erase(_items.begin() + i); break; }
    save();
    _pageNo = 0;
  } else if (op == "reset") {
    loadDefaults();
    save();
    _pageNo = 0;
  } else {
    return false;
  }
  buildPage();
  return true;
}
