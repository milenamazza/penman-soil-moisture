# Soil moisture forecasting with a FAO-56 Penman-Monteith water balance

A daily soil water balance (FAO-56, Allen et al. 1998) that forecasts the volumetric soil moisture measured by EM-500 probes from 1 to 7 days ahead. The model is driven by weather forecasts (rain and reference evapotranspiration ET0), crop coefficients (Kc) and logged irrigation events.


## Model

For every day D with an observed moisture value m(D), the balance is stepped forward one day at a time. At step h (day D+h):

```
Ks          = FAO-56 water stress coefficient (eq. 84), from m, FC, WP, p
ETc         = Ks * Kc(D+h) * ET0                    * mm_to_pct
rain        = alpha_rain * rain_mm                  * mm_to_pct
irrigation  =  efficiency * irrigation_mm   * mm_to_pct
percolation = 0.05 * (m - FC)            if m > FC, else 0
m           = clip(m + rain + irrigation - ETc - percolation, WP, 100)
```

- **Rain and ET0** are the Open-Meteo forecasts issued on day D for day D+h, i.e. the values available when the forecast is made.
- **Irrigation** is the amount logged for day D+h, treated as a known input.
- **Kc** follows the four-stage FAO-56 crop curve. It starts at the sowing date when known, otherwise at the sensor installation date.
- **`mm_to_pct`** converts millimetres of water into percentage points of volumetric moisture.
- **Missing inputs.** If an input is missing at step h, the chain stops and horizons h..7 have no forecast for that day. The inputs that can be missing are the weather forecast and Kc (outside the crop cycle).

### Parameters

| Parameter | Value | Description |
|---|---|---|
| `mm_to_pct` | 0.2 | mm of water → % volumetric moisture, for ETc, rain and irrigation |
| `alpha_rain` | 0.7 | fraction of rainfall reaching the probe |
| nominal irrigation efficiency | per field, `dati/campi.csv` | hose reel with rain gun: 0.60; hose reel with boom: 0.85 |
| FC, WP, p, Kc, stage lengths | per crop, `dati/colture.csv` | FAO-56 values (tables 11, 12, 22) |
| saturation | 100 | upper bound of simulated moisture (% vol) |

Model parameters are set in `penman/config.py` and can be overridden from the command line.

**Irrigation efficiency per field.** Each sensor installation (period) is matched to its field by sensor id and installation date, because the same sensor may have been moved between fields with different irrigation systems.

**Excluded irrigation.** Periods with `irrigazione_visibile = no` in `dati/campi.csv` get efficiency 0. This applies to sub-irrigation, where water enters from below and is not seen by the probe.

**No train/test split.** The water balance has no parameters fitted to the data, so errors are computed on every day with both a forecast and an observed value.

## Repository structure

```
esegui_penman.py      runs the model: loads data, simulates, writes forecasts and metrics
grafici.py            figures: error by horizon, t+1 scatter, t+1 time series per sensor
requirements.txt
penman/
  config.py           file paths and model parameters
  caricamento.py      raw dataset reader: probe moisture, station rainfall, weather forecasts
  anagrafica.py       crops, sensor periods, irrigation efficiency, irrigation log, Kc curve
  serie.py            daily per-sensor series on a complete calendar
  bilancio.py         water balance: stress coefficient, percolation, t+1..t+7 simulation
  valutazione.py      comparison with observations, error metrics
dati/
  sensori.csv         sensor periods: SENSORE, CAMPO, COLTURA, DATA INSTALLAZIONE,
                      DATA RIMOZIONE, DATA SEMINA (dd/mm/yyyy)
  campi.csv           per period: irrigation system, nominal efficiency, irrigazione_visibile (si/no)
  irrigazioni.csv     irrigation log: device_name, date, irrigation_mm
  colture.csv         FAO-56 crop parameters
output/               results of the run described below
```

Code identifiers and comments are in Italian.

## Data

The raw dataset (`dataset_pulito.csv`, about 1.7 GB) is not included. It is a long-format CSV, one reading per row, with columns `table, _time, _value, _field, _measurement, device_name`. Three quantities are extracted from it:

| Quantity | Source | Daily aggregation |
|---|---|---|
| soil moisture | `device_frmpayload_data_moisture` from `EM-500-*` devices | mean of readings in (0, 100] (UTC day) |
| measured rainfall | `device_frmpayload_data_rainfall_total` from `WS-*` stations | sum of positive counter increments per station, median across stations (UTC day) |
| forecast rain and ET0 | `openmeteo_previous_runs_hourly`, fields `rain` and `et0_fao_evapotranspiration` | hourly values summed per local day (Europe/Rome), per lead time 1–7 days |

Measured rainfall is used only in the figures; the model uses forecast rainfall.

## Usage

```
pip install -r requirements.txt
python esegui_penman.py --dataset path/to/dataset_pulito.csv
python grafici.py
```

The dataset path can also be given by copying the file to `dati/dataset_pulito.csv` or by setting the environment variable `AI_AGRI_DATASET`. Reading the dataset takes a few minutes.

Other parameters:

```
python esegui_penman.py --mm-to-pct 0.2 --alpha-rain 0.7 --a-corr 1.0 --out output_2
python grafici.py --risultati output_2
```

## Outputs

| File | Content |
|---|---|
| `output/previsioni.csv` | one row per (sensor, day D, horizon h): forecast and observed moisture at D+h, error, and the step inputs (Kc, Ks, forecast ET0 and rain, irrigation, efficiency) |
| `output/metriche.csv` | per horizon and overall: `n_osservati` (pairs with observed moisture at D and D+h), `n` (pairs with a forecast), MAE, RMSE, R², bias |
| `output/serie_giornaliere.csv` | per sensor and day: period, crop, observed moisture, forecast rain for that day, measured rain, logged and effective irrigation |
| `output/periodi.csv` | sensor periods with irrigation system and efficiency |
| `output/grafici/errore_per_orizzonte.png` | MAE and RMSE for every horizon, t+1 to t+7 |
| `output/grafici/osservato_vs_previsto.png` | observed vs forecast moisture at t+1 |
| `output/grafici/serie/` | one figure per sensor and period: observed and forecast moisture at t+1, with daily water inputs (forecast rain, measured rain, irrigation) |

Each forecast is plotted at the date it refers to (D+1).

## Results

15 sensors, 2025 and 2026 seasons, with the parameters listed above. Errors are in percentage points of volumetric moisture; bias is forecast minus observed.

| Horizon | n | MAE | RMSE | R² | Bias |
|---|---|---|---|---|---|
| t+1 | 1673 | 1.78 | 3.58 | 0.95 | −0.88 |
| t+2 | 1641 | 3.10 | 5.19 | 0.90 | −1.71 |
| t+3 | 1616 | 4.17 | 6.29 | 0.85 | −2.41 |
| t+4 | 1591 | 5.04 | 7.16 | 0.80 | −3.11 |
| t+5 | 1569 | 5.82 | 7.92 | 0.75 | −3.83 |
| t+6 | 1546 | 6.54 | 8.61 | 0.71 | −4.53 |
| t+7 | 1523 | 7.20 | 9.22 | 0.67 | −5.21 |
| all | 11159 | 4.75 | 7.04 | 0.81 | −3.05 |



## Notes


- **Forecast rainfall.** The model uses forecast rainfall, which is consistently lower than the rainfall measured by the stations and misses several heavy events. Part of the error on rainy days therefore comes from the weather forecast rather than from the water balance.
