# CLAUDE.md — home-assistant-comfoconnect (m7les fork)

Home Assistant custom component for the Zehnder ComfoAir Q, consuming the
`aiocomfoconnect` library. This is the **m7les fork** of
`michaelarnauts/home-assistant-comfoconnect`, targeting entity parity with (and
beyond) the ESPHome `yoziru/esphome-zehnder-comfoair` project.

## Repo / release (read before pushing)
- Working branch: `feat/entity-parity`.
- **Remotes:** `origin` = upstream (michaelarnauts) — pushing there 403s. The fork
  remote is named **`m7les`**. Always `git push m7les feat/entity-parity`.
- `manifest.json` pins the library by git tag:
  `aiocomfoconnect @ git+https://github.com/m7les/aiocomfoconnect@vX.Y.Z`.
  **Any change that calls a new library method requires: tag the library first, then
  bump this pin + the component `version`.** Otherwise the entity errors at runtime.
- Release order: library commit+tag+push → re-pin manifest → HA commit → push to `m7les`.

## Validation in this environment
- There is usually **no HA venv** here, so a full import test isn't possible. Validate
  with `python3 -c "import ast; ast.parse(...)"` on changed files, `json.load` on JSON,
  and the library's own pytest. `ruff` when available. The real end-to-end check is
  rebuilding a live HA against the branch.

## Core design principle
**All labelling / enum→text mapping lives here**, because the library returns raw
values. Prefer HA-idiomatic display: keep stable snake_case state values and add a
`translation_key` + entries in BOTH `strings.json` (2-space) and
`translations/en.json` (4-space, alphabetised). Don't bake display text into values.

## Patterns
- `EntityDescription`-tuple + dispatcher. Signal:
  `SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(uuid, sensor.id)`. `unique_id = {uuid}-{key}`.
- Two update models coexist:
  - **PDO push** (dispatcher) — most sensors/selects; `ccb_sensor=SENSORS.get(id)`.
  - **Polled** — `get_value_fn`/`set_value_fn` (selects, numbers, switches) and
    `ComfoConnectPropertySensor` in `sensor.py` for static RMI props.
- Platforms: fan, sensor, binary_sensor, select, number, switch, button, climate.
- Diagnostics: unknown PDOs (`PDO <id>`) and RMI property sensors are
  `EntityCategory.DIAGNOSTIC` + `entity_registry_enabled_default=False`.

## Boost model (deliberate — don't reintroduce the old sprawl)
- `sensor.operating_mode` (ENUM) = detection, incl. `bathroom_switch` for wall-button.
- `number.boost_duration` (RestoreNumber, minutes, **local HA preference**, 0 = until
  cancelled → protocol `-1`) is stored on `ccb.boost_duration_minutes`; `switch.boost`
  reads it on turn-on. This is NOT a unit setting.
- `button.cancel_bathroom_boost` cancels a wall-button boost (library `0x08`), which
  `switch.boost`/app-boost cannot. **TODO: still needs live end-to-end verification.**
- Removed on purpose: the janky `select.boost_timeout` and the timed boost buttons
  (`boost_1h/3h/12h`, `boost_off`). Timed boost = the duration number + switch, or an
  automation. Do not add per-duration entities back.

## Bathroom-switch installer settings
Writable ones are `number` entities (CONFIG, disabled by default):
`bathroom_switch_boost_duration` (0x0c, min), `bathroom_switch_activation_delay`
(0x0b, s). Mode (0x0d) is a read-only diagnostic sensor (unit ignores writes).

## Hardware
Reference unit: ComfoAir Q350 via bridge `comfoconnect_lan_c.jtt.lfnt.xyz` (Tailscale).
Prod HA token lives in `~/claude/passivehaus-analysis/config/.secrets.env` (`HA_TOKEN`) —
never print/commit tokens; prod operations read-only unless explicitly authorised.
