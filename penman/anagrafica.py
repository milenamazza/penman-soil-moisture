"""
Informazioni agronomiche e di campo:

  colture       parametri FAO-56 per coltura (dati/colture.csv)
  periodi       un periodo per ogni riga di dati/sensori.csv: sensore, campo,
                coltura, date di installazione, rimozione e semina, con
                l'efficacia nominale dell'irrigazione del campo (dati/campi.csv)
  irrigazioni   registro delle irrigazioni (dati/irrigazioni.csv)
  curva Kc      coefficiente colturale giorno per giorno
"""

from io import StringIO

import numpy as np
import pandas as pd


def carica_colture(percorso):
    """Parametri FAO-56 indicizzati per coltura. Le righe che iniziano con #
    sono commenti."""
    righe = [r for r in open(percorso, encoding="utf-8") if not r.strip().startswith("#")]
    colture = pd.read_csv(StringIO("".join(righe)))
    colture["coltura"] = colture["coltura"].str.strip().str.lower()
    return colture.set_index("coltura")


def carica_periodi(percorso_sensori, percorso_campi):
    """Un periodo per ogni installazione di un sensore, con l'efficacia
    nominale dell'irrigazione del suo campo.

    L'abbinamento con dati/campi.csv è per (sensore, data di installazione):
    lo stesso sensore può essere stato in campi diversi, con sistemi di
    irrigazione diversi. Se un periodo non ha la riga corrispondente in
    dati/campi.csv viene sollevato un errore.

    Colonne: sensore, campo, coltura, installazione, rimozione, origine_kc,
    sistema_irrigazione, efficacia, irrigazione_visibile, periodo.
    """
    s = pd.read_csv(percorso_sensori)
    s.columns = s.columns.str.strip()
    periodi = pd.DataFrame({
        "sensore": "EM-500-" + pd.to_numeric(s["SENSORE"], errors="coerce").astype(int).astype(str),
        "campo": s["CAMPO"].str.strip(),
        "coltura": s["COLTURA"].str.strip().str.lower(),
        "installazione": pd.to_datetime(s["DATA INSTALLAZIONE"], dayfirst=True, errors="coerce"),
        "rimozione": pd.to_datetime(s["DATA RIMOZIONE"], dayfirst=True, errors="coerce"),
        "semina": pd.to_datetime(s["DATA SEMINA"], dayfirst=True, errors="coerce"),
    }).dropna(subset=["installazione"])
    # La curva Kc descrive lo sviluppo della pianta: parte dalla semina quando
    # è nota, dall'installazione del sensore altrimenti.
    periodi["origine_kc"] = periodi["semina"].fillna(periodi["installazione"])

    campi = pd.read_csv(percorso_campi, parse_dates=["installazione"])
    campi["sensore"] = "EM-500-" + campi["sensore"].astype(int).astype(str)
    periodi = periodi.merge(
        campi[["sensore", "installazione", "sistema_irrigazione", "efficacia",
               "irrigazione_visibile"]],
        on=["sensore", "installazione"], how="left")
    scoperti = periodi[periodi["efficacia"].isna()]
    if not scoperti.empty:
        raise ValueError(f"Periodi senza riga in {percorso_campi}:\n"
                         + scoperti[["sensore", "campo", "installazione"]].to_string(index=False))
    # Dove l'acqua arriva da sotto (subirrigazione) la sonda non vede
    # l'irrigazione: quelle irrigazioni non entrano nel bilancio.
    periodi["irrigazione_visibile"] = periodi["irrigazione_visibile"].str.strip() == "si"

    # etichetta leggibile del periodo: <n>_<coltura>_<installazione>
    periodi = periodi.sort_values(["sensore", "installazione"]).reset_index(drop=True)
    n = periodi.groupby("sensore").cumcount() + 1
    periodi["periodo"] = (n.astype(str) + "_" + periodi["coltura"] + "_"
                          + periodi["installazione"].dt.strftime("%Y-%m-%d"))
    return periodi.drop(columns="semina")


def carica_irrigazioni(percorso):
    """mm irrigati per (sensore, data). Più righe sullo stesso giorno si sommano."""
    irr = pd.read_csv(percorso, parse_dates=["date"])
    irr["date"] = irr["date"].dt.normalize()
    return (irr.groupby(["device_name", "date"], as_index=False)["irrigation_mm"].sum()
            .rename(columns={"device_name": "sensore", "date": "data",
                             "irrigation_mm": "irrigazione_mm"}))


def curva_kc(origine, coltura):
    """Kc giorno per giorno dalla data di origine, interpolato linearmente fra
    le quattro fasi FAO-56: iniziale (Kc_ini costante), sviluppo (da Kc_ini a
    Kc_mid), piena vegetazione (Kc_mid costante), fine ciclo (da Kc_mid a
    Kc_end). Fuori dal ciclo la curva non è definita."""
    fine_ini = coltura["lini"]
    fine_dev = fine_ini + coltura["ldev"]
    fine_mid = fine_dev + coltura["lmid"]
    totale = int(fine_mid + coltura["llate"])
    giorni = np.arange(0, totale + 1)
    kc = np.interp(giorni,
                   [0, fine_ini, fine_dev, fine_mid, totale],
                   [coltura["kc_ini"], coltura["kc_ini"], coltura["kc_mid"],
                    coltura["kc_mid"], coltura["kc_end"]])
    return pd.Series(kc, index=pd.date_range(origine, periods=totale + 1, freq="D"))
