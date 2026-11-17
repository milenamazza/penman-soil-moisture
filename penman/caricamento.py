"""
Lettura del dataset grezzo (dataset_pulito.csv).

Il file è in formato lungo, una lettura per riga (_time, _value, _field,
_measurement, device_name, table). Se ne estraggono tre cose:

  umidità     media giornaliera dell'umidità del suolo di ogni sonda EM-500
  pioggia     pioggia misurata giornaliera, mediana fra le stazioni meteo WS
  previsioni  pioggia ed ET0 previste da Open-Meteo, per giorno di emissione e
              orizzonte da 1 a 7 giorni

I giorni delle letture delle sonde e delle stazioni sono giorni di calendario
UTC; quelli delle previsioni sono giorni locali (Europe/Rome).
"""

import pandas as pd

PREFISSO = "device_frmpayload_data_"
MISURA_UMIDITA = PREFISSO + "moisture"
MISURA_PIOGGIA = PREFISSO + "rainfall_total"
MISURA_PREVISIONI = "openmeteo_previous_runs_hourly"
COLONNE = ["table", "_time", "_value", "_field", "_measurement", "device_name"]

# Il contatore di pioggia delle stazioni usa 600 come valore di errore.
SENTINELLA_PIOGGIA = 600.0

# Le previsioni sono salvate in blocchi di 18 tabelle consecutive, una per
# campo, e ogni blocco ha un orizzonte fisso. Il primo campo di ogni blocco è
# apparent_temperature.
TABELLE_PER_BLOCCO = 18
PRIMO_CAMPO_BLOCCO = "apparent_temperature"
FUSO_PREVISIONI = "Europe/Rome"
# campo Open-Meteo -> nome usato qui; sono valori orari da sommare sul giorno
CAMPI_PREVISIONE = {"rain": "pioggia", "et0_fao_evapotranspiration": "et0"}


def carica_dataset(percorso, righe_per_blocco=1_000_000):
    """Legge il dataset a blocchi e restituisce (umidita, pioggia, previsioni):

      umidita     sensore, data, umidita (% vol, media giornaliera)
      pioggia     data, pioggia_misurata_mm
      previsioni  data_emissione, orizzonte, pioggia_mm, et0_mm

    Pulizia: si scartano le letture di umidità fuori da (0, 100], che sono
    letture rotte della sonda, e le letture di pioggia uguali o superiori al
    valore di errore del contatore.
    """
    sonde, stazioni, grezze_previsioni = [], [], []
    print(f"Leggo {percorso} ...")
    for i, blocco in enumerate(pd.read_csv(percorso, usecols=COLONNE,
                                           chunksize=righe_per_blocco, low_memory=False)):
        blocco["_time"] = pd.to_datetime(blocco["_time"], utc=True, format="ISO8601",
                                         errors="coerce")
        blocco = blocco.dropna(subset=["_time"])
        misura = blocco["_measurement"]
        valore = pd.to_numeric(blocco["_value"], errors="coerce")
        dispositivo = blocco["device_name"].fillna("").astype(str)

        e_sonda = (dispositivo.str.match(r"^EM-500-\d+$") & (misura == MISURA_UMIDITA)
                   & (valore > 0) & (valore <= 100))
        e_stazione = (dispositivo.str.startswith("WS-") & (misura == MISURA_PIOGGIA)
                      & valore.notna() & (valore < SENTINELLA_PIOGGIA))

        sonde.append(pd.DataFrame({"sensore": dispositivo[e_sonda],
                                   "tempo": blocco.loc[e_sonda, "_time"],
                                   "valore": valore[e_sonda]}))
        stazioni.append(pd.DataFrame({"stazione": dispositivo[e_stazione],
                                      "tempo": blocco.loc[e_stazione, "_time"],
                                      "valore": valore[e_stazione]}))
        grezze_previsioni.append(blocco.loc[misura == MISURA_PREVISIONI,
                                            ["table", "_time", "_value", "_field"]])
        print(f"  blocco {i + 1}", end="\r")
    print()

    umidita = _umidita_giornaliera(pd.concat(sonde, ignore_index=True))
    pioggia = _pioggia_giornaliera(pd.concat(stazioni, ignore_index=True))
    previsioni = _previsioni_giornaliere(pd.concat(grezze_previsioni, ignore_index=True))
    print(f"  umidità: {len(umidita)} giorni-sonda; pioggia misurata: {len(pioggia)} giorni; "
          f"previsioni: {len(previsioni)} giorni-orizzonte")
    return umidita, pioggia, previsioni


def _giorno_utc(tempo):
    return tempo.dt.normalize().dt.tz_localize(None)


def _umidita_giornaliera(letture):
    letture["data"] = _giorno_utc(letture["tempo"])
    return (letture.groupby(["sensore", "data"], as_index=False)["valore"].mean()
            .rename(columns={"valore": "umidita"}))


def _pioggia_giornaliera(letture):
    """Il contatore di pioggia di ogni stazione è cumulativo e si azzera ogni
    tanto. La pioggia del giorno è la somma degli incrementi positivi fra
    letture consecutive (gli azzeramenti contano zero), calcolati sull'intera
    serie della stazione. Fra le stazioni attive si prende la mediana, che non
    risente di una singola stazione che segna pioggia per errore."""
    letture["data"] = _giorno_utc(letture["tempo"])
    per_stazione = []
    for nome, g in letture.groupby("stazione"):
        g = g.sort_values("tempo")
        incrementi = g["valore"].diff().clip(lower=0).fillna(0)
        per_stazione.append(incrementi.groupby(g["data"]).sum().rename(nome))
    mediana = pd.concat(per_stazione, axis=1).median(axis=1)
    return mediana.rename("pioggia_misurata_mm").rename_axis("data").reset_index()


def _previsioni_giornaliere(grezze):
    """Ricostruisce le previsioni orarie da ogni blocco di tabelle (orizzonte =
    giorni fra l'emissione e l'ora prevista) e le somma per giorno locale. La
    previsione per il giorno X con orizzonte h è attribuita al giorno di
    emissione X - h: è quella che si conosce il giorno X - h."""
    campo_per_tabella = grezze.groupby("table")["_field"].first()
    inizi = sorted(campo_per_tabella[campo_per_tabella == PRIMO_CAMPO_BLOCCO].index)

    orarie = []
    for inizio in inizi:
        sub = grezze[grezze["table"].isin(range(inizio, inizio + TABELLE_PER_BLOCCO))]
        tab = sub.pivot_table(index="_time", columns="_field", values="_value",
                              aggfunc="first").reset_index()
        if "target_time_iso" not in tab or "reference_time_iso" not in tab:
            continue
        prevista = pd.to_datetime(tab["target_time_iso"], errors="coerce", utc=True)
        emessa = pd.to_datetime(tab["reference_time_iso"], errors="coerce", utc=True)
        valide = prevista.notna() & emessa.notna()
        if not valide.any():
            continue
        orizzonte = round(float((prevista[valide] - emessa[valide]).dt.total_seconds()
                                .median() / 86400))
        if orizzonte not in range(1, 8):
            continue
        for campo, nome in CAMPI_PREVISIONE.items():
            if campo not in tab:
                continue
            o = pd.DataFrame({"tempo": prevista[valide],
                              "valore": pd.to_numeric(tab.loc[valide, campo], errors="coerce")})
            o = o.dropna(subset=["valore"])
            o["orizzonte"] = orizzonte
            o["campo"] = nome
            orarie.append(o)

    orarie = pd.concat(orarie, ignore_index=True)
    giorno = orarie["tempo"].dt.tz_convert(FUSO_PREVISIONI).dt.normalize().dt.tz_localize(None)
    orarie["data_emissione"] = giorno - pd.to_timedelta(orarie["orizzonte"], unit="D")
    giornaliere = (orarie.groupby(["data_emissione", "orizzonte", "campo"])["valore"].sum()
                   .unstack("campo").reset_index())
    giornaliere.columns.name = None
    return giornaliere.rename(columns={"pioggia": "pioggia_mm", "et0": "et0_mm"})
