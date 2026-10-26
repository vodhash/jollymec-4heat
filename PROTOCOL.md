# 4HEAT cloud protocol (Tiemme Elettronica) — Jolly Mec Connect

Reverse-engineered for local Home Assistant control of a Jolly Mec Synthesis
Modular pellet insert fitted with a Tiemme "4heatlite" Wi-Fi module.
Device under study: id `26011141`, product `SYEVO0000559`, `comunicazione: 2ways`.

## Architecture

The module is cloud-only. It opens no usable local port (local port 80 answers
6 null bytes, not the classic 4heat JSON socket protocol). All control goes
through an Azure backend, in cleartext or TLS.

Mailbox pattern:
- The ESP32 module polls the cloud every ~60 s for queued commands, runs them,
  and reports its state back to the cloud.
- Clients (the app, this project) read the last reported state and push commands
  into the queue. They never talk to the module directly.

```
client ──POST command──▶ cloud queue ──poll──▶ module ──state──▶ cloud ──GET summary──▶ client
```

## Endpoints

Base: `https://wifi4heat.azurewebsites.net` (app, TLS 443).
The module itself uses `http://wifi4heat-linux.azurewebsites.net` (cleartext 80),
same routes. Both resolve to the same Azure App Service (.NET / Kestrel).

| Method | Path | Auth | Use |
|---|---|---|---|
| GET  | `/api/devices/summary?ids=<id>` | none | **state read** (last reported message) |
| GET  | `/api/Devices/FileMap?pin=<pin>&id=<id>` | none | register map + command defs |
| GET  | `/api/Devices/DetailsCustomer?id=<id>` | none | name, customer id |
| POST | `/api/devices/command` | **bearer** | **send command** `{id, comando:[...]}` |
| GET  | `/api/devices/commands?id=<id>&removefromserver=<bool>` | none | module's command inbox (module-facing) |
| GET  | `/api/devices/realTime?id=<id>` | bearer | on-demand read (not needed) |
| GET  | `/api/Devices/Details?id=<id>` | bearer | details (not needed) |
| POST | `/Token` | — | OAuth2 password grant → bearer token (~14 day TTL) |

Auth reality: reads are open, writes are not.
- Open (no token): `summary`, `FileMap`, `DetailsCustomer`, the module-facing
  `commands` inbox. The app's literal `Authorization: Bearer @token` placeholder
  works here because it is ignored.
- Bearer required: `command` (write), `realTime`, `Details`, `DeviceLiteType`.
  A real token comes from `POST /Token` with `grant_type=password` and a myJOLLY
  MEC account's email/password. A bogus bearer gives 401 (verified: the write POST
  401s without a valid token; a GET on the POST route 405s *before* auth, which is
  why a method probe is misleading). Token TTL ~14 days; refresh via `/Token`.

So the integration reads state from `summary` unauthenticated, and needs one
account login for writes only.

Default device PIN is `000000` (gates FileMap only; not a transport credential).

## State read

`GET /api/devices/summary?ids=<id>` returns a one-element array:

```jsonc
{
  "Id": "26011141", "Name": "Insert", "IsOnline": true,
  "FirmwareVersion": 2, "FirmwareRevision": 11, "IpAddress": "192.168.0.79",
  "FilemapHash": "4308028a…",           // cache key for FileMap
  "LastTimestamp": "2026-10-25T21:17:58",
  "LastMessageReceived": "{ \"DeviceKey\": \"…\", \"TimeStamp\": \"…\",
                            \"GmtOffset\": 3600, \"Values\": [ \"<hex frame>\", … ] }"
}
```

`LastMessageReceived` is a JSON **string**; parse it, then read `Values[]`.

## Value frames (2ways)

Each `Values[]` entry is a hex frame. Byte 0 is the type; offsets below are in
hex chars. 16-bit fields are signed (`v-65536 if v>32767`). Faithful port of the
app's `SERVIZI2W.estraivalori`; see `decode_frame` in `jm4heat.py`.

| Type (hex / dec) | name | key fields (hex-char offsets) |
|---|---|---|
| `12` / 18 | testout     | reg=`[2:6]` value=`[6:10]` min=`[10:14]` max=`[14:18]` pos_punto=`[20:22]` |
| `0e` / 14 | par_value   | reg=`[2:6]` value=`[6:10]` min=`[10:14]` max=`[14:18]` pos_punto=`[20:22]` |
| `10` / 16 | main_values | temp_sec=`[6:10]` **stato=`[10:12]`** **errore=`[12:14]`** temp_princ=`[20:24]` |
| `0c81`    | state_info_81 | liv_pot=char`[6:8]` termostato=`[24:28]` |
| `02` / 2  | th_temp     | reg=`[2:4]` value=`[6:10]` |
| `06` / 6  | pw_all      | reg=`[2:4]` value=`[4:6]` min=`[6:8]` max=`[8:10]` |
| `22` / 34 | th_all_2    | value=`[10:14]` min=`[14:18]` max=`[18:22]` temperatura=`[26:30]` |

`value` is scaled by FileMap `moltiplicatore` and divided by `10^pos_punto`.

### Values ↔ FileMap alignment

`Values[]` is positionally aligned with `comandi_log[]` entries having
`flag_server == true`, same order (entries with `flag_server == false`, e.g.
`131_SINOTTICO 4WEB`, are not reported). Each `comandi_log` entry gives the label
(`cod_comando` = `"<id>_<label>"`), `unita`, `moltiplicatore`. The frame also
self-identifies its register, so the mapping can be cross-checked.

Register map for this device (SYEVO0000559), the reported sensors:

| comando | label | unit |
|---|---|---|
| `0310`     | MAINVALUES (state/error/room temp) | |
| `030C81`   | INFO81 (power level, setpoint) | |
| `0312FFFF` | Temperatura Fumi (flue) | °C |
| `0312FFF7` | Temperatura Ambiente (room) | °C |
| `0312FFE0` | Temperatura Ambiente remota | °C |
| `0312FFED` | Flusso aria | % |
| `030E016C` | Potenza combustione | Nr |
| `030E023F` | Potenza riscaldamento | Nr |
| `030E0266` | Potenza canalizzata 1 | Nr |
| `0312FFDF` | SERVICE 4WEB (diagnostic bitfield) | |
| `0312FFDE` | CLEANING 4WEB | |
| `030E027E` | Potenza canalizzata 2 | Nr |
| `0312005A` | **Termostato Ambiente (setpoint)** | °C |

### States (`lingue_stati`) and errors (`codici_errori`)

`main_values.stato` → `lingue_stati[val]`:
`0 OFF · 1 CHECK UP · 2 IGNITION · 3 STABILISATION · 4 RETRY IGNITION ·
5 RUN MODE · 6 MODULATION · 7 EXTINGUISHING · 8 SAFETY MODE · 9 BLOCK ·
10 RECOVER IGNITION · 11 STANDBY · 13 RUN MODE M · 30-34 IGNITION`.

`main_values.errore` indexes `codici_errori` (0 = `----` none, 1 = `Er01`, …).

## Commands (write)

`POST /api/devices/command`, body `{ "id": "<id>", "comando": [<array>] }`,
`Content-Type: application/json`, `Authorization: Bearer <token>`. `comando` is
the split of a string:
- 2ways (this device): `["2WC","1","<hexcode>"]`
- legacy syevo: `["SEC","1","<Jcode>"]`

Write opcode is `05` (read opcode is `03`).

From FileMap `comandi_on_off`:
- ON  (accensione): `["2WC","1","05040000"]`
- OFF (spegnimento): `["2WC","1","05050000"]`
- unblock (sblocco): `["2WC","1","05050000"]`

Setpoint (register `005A`, `comandi_term_princ`): the app builds the write by
prefixing `05` to the register's current read frame and overwriting the value
field (`aggiornacomando2w`). For a type-`12` frame `12 005A vvvv mmmm MMMM …`:

```
["2WC","1","05" + "12005A" + <value hex, 4 chars> + <tail of read frame from offset 10>]
```

e.g. setpoint 21 °C → `0512005A0015000A00280000000100`. **Validated on hardware**:
POST returned 200 and `summary` reflected setpoint 20 → 21 within ~30 s.

ON/OFF (`05040000` / `05050000`) validated on hardware: OFF took the stove from
MODULATION (6) to EXTINGUISHING (7) within 30 s and on to OFF; ON is symmetric.

### Menu parameters (settable)

`comandi_menu` is a tree; every node with a non-empty `comando` is a settable
parameter, written the same way as the setpoint: prefix `05` to the parameter's
current read frame and overwrite the value field. `aggiornacomando2w` picks the
value offsets from the frame type (first byte):

| Type | Write frame |
| ---- | ----------- |
| `01` | `05` + read[0:10] + value(2) + read[12:] |
| `06` | `05` + read[0:4] + value(2) + read[6:10] |
| `0E` | `05` + read[0:6] + value(4) |
| `12` | `05` + read[0:6] + value(4) + read[10:28] |
| `22` | `05` + read[0:10] + value(4) + read[14:] |

Nodes with `cenums` are enumerations (`{val → descrizione}`); the rest are numeric
(bounds from the frame's min/max). Confirmed settable on this device (all present
in `comandi_log`, so their live value and bounds come from `summary`):

- `030E016C` combustion power, `030E023F` heating power — enum P1-P6/Auto, visible
- `030E0266` / `030E027E` ducted power 1 / 2 — enum, hidden
- `030E0231` temperature source selector — enum Local/Remote/Local-Remote, hidden
- `03120058` / `03120059` remote room 1 / 2 — numeric, hidden

Validated on hardware: the setpoint (type `12`) and the combustion power (type `0E`,
`030E016C`, P2 -> P3 -> P2, applied and read back within ~40-60 s). All settable menu
parameters on this device are type `0E` (enums) or `12` (remote rooms), so both write
encoders are confirmed live. Types `01`, `06`, `22` are implemented from the app but
not exercised here.

## Open items

- State freshness: `summary` reflects the module's last spontaneous report; it
  updated ~30 s after the write here. Measure cadence before fixing the HA poll
  interval (≥ 30 s).
- Diagnostic registers (`FFDF` SERVICE, `FFDE` CLEANING) carry packed values, not
  the °C their FileMap unit suggests; exclude or decode separately.
- Local control (TCP port 80, after UDP 5555 discovery) is intermittent across
  VLANs and unreliable here; cloud is the supported path.
