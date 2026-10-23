// Сгенерировано tools/gen_panel_schema.py из spec/dp.json. Руками не править.
export const defaultSchema = [
  {
    "attr": 0,
    "canTrigger": true,
    "code": "rain",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 101,
    "mode": "ro",
    "name": "rain",
    "property": {
      "type": "bool"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "night",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 102,
    "mode": "ro",
    "name": "night",
    "property": {
      "type": "bool"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "pump",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 103,
    "mode": "ro",
    "name": "pump",
    "property": {
      "type": "bool"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "drain",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 104,
    "mode": "ro",
    "name": "drain",
    "property": {
      "type": "bool"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "fill",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 105,
    "mode": "ro",
    "name": "fill",
    "property": {
      "type": "bool"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "flow_rate",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 106,
    "mode": "ro",
    "name": "flow_rate",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100000,
      "scale": 3,
      "step": 1,
      "unit": "л/мин"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "flow_session",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 107,
    "mode": "ro",
    "name": "flow_session",
    "property": {
      "type": "value",
      "min": 0,
      "max": 10000000,
      "scale": 2,
      "step": 1,
      "unit": "л"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "flow_total",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 108,
    "mode": "ro",
    "name": "flow_total",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100000000,
      "scale": 1,
      "step": 1,
      "unit": "л"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "fault",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 109,
    "mode": "ro",
    "name": "fault",
    "property": {
      "type": "bitmap",
      "label": [
        "rtc",
        "sd",
        "valves",
        "filter_clog"
      ],
      "maxlen": 4
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "filter_baseline",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 110,
    "mode": "ro",
    "name": "filter_baseline",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100000,
      "scale": 3,
      "step": 1,
      "unit": "л/мин"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "run_on_rain",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 111,
    "mode": "rw",
    "name": "run_on_rain",
    "property": {
      "type": "bool"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "run_on_night",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 112,
    "mode": "rw",
    "name": "run_on_night",
    "property": {
      "type": "bool"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "delta_hum",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 113,
    "mode": "rw",
    "name": "delta_hum",
    "property": {
      "type": "value",
      "min": 0,
      "max": 50,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "delta_calib",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 114,
    "mode": "rw",
    "name": "delta_calib",
    "property": {
      "type": "value",
      "min": 0,
      "max": 500,
      "scale": 0,
      "step": 1,
      "unit": "АЦП"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "boost_pump_valves",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 115,
    "mode": "rw",
    "name": "boost_pump_valves",
    "property": {
      "type": "value",
      "min": 1,
      "max": 9,
      "scale": 0,
      "step": 1,
      "unit": ""
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "clog_threshold",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 116,
    "mode": "rw",
    "name": "clog_threshold",
    "property": {
      "type": "value",
      "min": 10,
      "max": 95,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "flow_monitor",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 117,
    "mode": "rw",
    "name": "flow_monitor",
    "property": {
      "type": "bool"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "autocal_no_delay",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 118,
    "mode": "rw",
    "name": "autocal_no_delay",
    "property": {
      "type": "bool"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": false,
    "code": "command",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 119,
    "mode": "wr",
    "name": "command",
    "property": {
      "type": "enum",
      "range": [
        "restart",
        "reset_settings",
        "clear_flow",
        "filter_cleaned",
        "drain"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": false,
    "code": "mode_all",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 120,
    "mode": "wr",
    "name": "mode_all",
    "property": {
      "type": "enum",
      "range": [
        "auto",
        "on",
        "off",
        "greenhouse"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": false,
    "code": "wizard",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 121,
    "mode": "wr",
    "name": "wizard",
    "property": {
      "type": "string",
      "maxlen": 255
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "wizard_state",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 122,
    "mode": "ro",
    "name": "wizard_state",
    "property": {
      "type": "string",
      "maxlen": 255
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "adc_raw",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 123,
    "mode": "ro",
    "name": "adc_raw",
    "property": {
      "type": "raw",
      "maxlen": 128
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "event",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 124,
    "mode": "ro",
    "name": "event",
    "property": {
      "type": "string",
      "maxlen": 255
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "pump_state",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 125,
    "mode": "ro",
    "name": "pump_state",
    "property": {
      "type": "enum",
      "range": [
        "off",
        "start",
        "valves",
        "drain"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "sys_info",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 126,
    "mode": "ro",
    "name": "sys_info",
    "property": {
      "type": "string",
      "maxlen": 255
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "pump_start_sec",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 127,
    "mode": "rw",
    "name": "pump_start_sec",
    "property": {
      "type": "value",
      "min": 0,
      "max": 600,
      "scale": 0,
      "step": 1,
      "unit": "с"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "humidity_1",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 131,
    "mode": "ro",
    "name": "humidity_1",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "humidity_2",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 132,
    "mode": "ro",
    "name": "humidity_2",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "humidity_3",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 133,
    "mode": "ro",
    "name": "humidity_3",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "humidity_4",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 134,
    "mode": "ro",
    "name": "humidity_4",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "humidity_5",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 135,
    "mode": "ro",
    "name": "humidity_5",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "humidity_6",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 136,
    "mode": "ro",
    "name": "humidity_6",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "humidity_7",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 137,
    "mode": "ro",
    "name": "humidity_7",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "humidity_8",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 138,
    "mode": "ro",
    "name": "humidity_8",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "valve_1",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 141,
    "mode": "ro",
    "name": "valve_1",
    "property": {
      "type": "enum",
      "range": [
        "init",
        "open_hum",
        "close_hum",
        "hyst",
        "forced_open",
        "forced_close"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "valve_2",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 142,
    "mode": "ro",
    "name": "valve_2",
    "property": {
      "type": "enum",
      "range": [
        "init",
        "open_hum",
        "close_hum",
        "hyst",
        "forced_open",
        "forced_close"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "valve_3",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 143,
    "mode": "ro",
    "name": "valve_3",
    "property": {
      "type": "enum",
      "range": [
        "init",
        "open_hum",
        "close_hum",
        "hyst",
        "forced_open",
        "forced_close"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "valve_4",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 144,
    "mode": "ro",
    "name": "valve_4",
    "property": {
      "type": "enum",
      "range": [
        "init",
        "open_hum",
        "close_hum",
        "hyst",
        "forced_open",
        "forced_close"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "valve_5",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 145,
    "mode": "ro",
    "name": "valve_5",
    "property": {
      "type": "enum",
      "range": [
        "init",
        "open_hum",
        "close_hum",
        "hyst",
        "forced_open",
        "forced_close"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "valve_6",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 146,
    "mode": "ro",
    "name": "valve_6",
    "property": {
      "type": "enum",
      "range": [
        "init",
        "open_hum",
        "close_hum",
        "hyst",
        "forced_open",
        "forced_close"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "valve_7",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 147,
    "mode": "ro",
    "name": "valve_7",
    "property": {
      "type": "enum",
      "range": [
        "init",
        "open_hum",
        "close_hum",
        "hyst",
        "forced_open",
        "forced_close"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "valve_8",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": false,
    "extContent": "",
    "iconname": "",
    "id": 148,
    "mode": "ro",
    "name": "valve_8",
    "property": {
      "type": "enum",
      "range": [
        "init",
        "open_hum",
        "close_hum",
        "hyst",
        "forced_open",
        "forced_close"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "mode_1",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 151,
    "mode": "rw",
    "name": "mode_1",
    "property": {
      "type": "enum",
      "range": [
        "auto",
        "on",
        "off",
        "greenhouse"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "mode_2",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 152,
    "mode": "rw",
    "name": "mode_2",
    "property": {
      "type": "enum",
      "range": [
        "auto",
        "on",
        "off",
        "greenhouse"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "mode_3",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 153,
    "mode": "rw",
    "name": "mode_3",
    "property": {
      "type": "enum",
      "range": [
        "auto",
        "on",
        "off",
        "greenhouse"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "mode_4",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 154,
    "mode": "rw",
    "name": "mode_4",
    "property": {
      "type": "enum",
      "range": [
        "auto",
        "on",
        "off",
        "greenhouse"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "mode_5",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 155,
    "mode": "rw",
    "name": "mode_5",
    "property": {
      "type": "enum",
      "range": [
        "auto",
        "on",
        "off",
        "greenhouse"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "mode_6",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 156,
    "mode": "rw",
    "name": "mode_6",
    "property": {
      "type": "enum",
      "range": [
        "auto",
        "on",
        "off",
        "greenhouse"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "mode_7",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 157,
    "mode": "rw",
    "name": "mode_7",
    "property": {
      "type": "enum",
      "range": [
        "auto",
        "on",
        "off",
        "greenhouse"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "mode_8",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 158,
    "mode": "rw",
    "name": "mode_8",
    "property": {
      "type": "enum",
      "range": [
        "auto",
        "on",
        "off",
        "greenhouse"
      ]
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "border_1",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 161,
    "mode": "rw",
    "name": "border_1",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "border_2",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 162,
    "mode": "rw",
    "name": "border_2",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "border_3",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 163,
    "mode": "rw",
    "name": "border_3",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "border_4",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 164,
    "mode": "rw",
    "name": "border_4",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "border_5",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 165,
    "mode": "rw",
    "name": "border_5",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "border_6",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 166,
    "mode": "rw",
    "name": "border_6",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "border_7",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 167,
    "mode": "rw",
    "name": "border_7",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "border_8",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 168,
    "mode": "rw",
    "name": "border_8",
    "property": {
      "type": "value",
      "min": 0,
      "max": 100,
      "scale": 0,
      "step": 1,
      "unit": "%"
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "name_1",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 171,
    "mode": "rw",
    "name": "name_1",
    "property": {
      "type": "string",
      "maxlen": 32
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "name_2",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 172,
    "mode": "rw",
    "name": "name_2",
    "property": {
      "type": "string",
      "maxlen": 32
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "name_3",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 173,
    "mode": "rw",
    "name": "name_3",
    "property": {
      "type": "string",
      "maxlen": 32
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "name_4",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 174,
    "mode": "rw",
    "name": "name_4",
    "property": {
      "type": "string",
      "maxlen": 32
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "name_5",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 175,
    "mode": "rw",
    "name": "name_5",
    "property": {
      "type": "string",
      "maxlen": 32
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "name_6",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 176,
    "mode": "rw",
    "name": "name_6",
    "property": {
      "type": "string",
      "maxlen": 32
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "name_7",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 177,
    "mode": "rw",
    "name": "name_7",
    "property": {
      "type": "string",
      "maxlen": 32
    },
    "type": "obj"
  },
  {
    "attr": 0,
    "canTrigger": true,
    "code": "name_8",
    "defaultRecommend": false,
    "editPermission": false,
    "executable": true,
    "extContent": "",
    "iconname": "",
    "id": 178,
    "mode": "rw",
    "name": "name_8",
    "property": {
      "type": "string",
      "maxlen": 32
    },
    "type": "obj"
  }
] as const;
