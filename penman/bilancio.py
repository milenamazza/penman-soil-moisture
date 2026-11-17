"""
Bilancio idrico FAO-56 simulato in avanti da t+1 a t+7.

Per ogni giorno D con l'umidità osservata si parte da m = umidità(D) e si
avanza un giorno alla volta. Al passo h (giorno D+h):

    Ks       = stress idrico FAO-56 (eq. 84) da m, FC, WP, p
    ETc      = Ks * Kc(D+h) * ET0                    * mm_to_pct
    pioggia  = alpha_rain * pioggia_mm               * mm_to_pct
    irrig.   = a_corr * efficacia * irrigazione_mm   * mm_to_pct
    perc.    = percolazione sopra la capacità di campo
    m        = clip(m + pioggia + irrig. - ETc - perc., WP, SATURAZIONE)

ET0 e pioggia sono le previsioni meteo emesse il giorno D per il giorno D+h,
cioè i valori disponibili al momento della previsione. L'irrigazione è quella
registrata per il giorno D+h, trattata come input noto in anticipo.
mm_to_pct converte i mm d'acqua in punti % di umidità volumetrica.

Se al passo h manca un input (previsione meteo, oppure Kc perché il giorno
cade fuori dal ciclo della coltura) la catena si interrompe: gli orizzonti da
h in poi restano senza previsione per quel giorno.
"""

import numpy as np
import pandas as pd

from .anagrafica import curva_kc
from .config import COEFF_PERCOLAZIONE, ORIZZONTI, SATURAZIONE


def stress_idrico(m, fc, wp, p):
    """Coefficiente Ks (FAO-56 eq. 84): 1 finché l'acqua disponibile non scende
    sotto la soglia p*(FC - WP), poi cala linearmente fino a 0 al punto di
    appassimento."""
    taw = fc - wp                 # acqua totale disponibile
    raw = p * taw                 # acqua facilmente disponibile
    if m >= fc - raw:
        return 1.0
    if m <= wp:
        return 0.0
    return (taw - (fc - m)) / (taw - raw)


def percolazione(m, fc):
    """Drenaggio profondo: una frazione dell'eccesso sopra la capacità di campo."""
    if m > fc:
        eccesso = m - fc
        return min(eccesso * COEFF_PERCOLAZIONE, eccesso)
    return 0.0


def simula(serie, periodi, colture, mm_to_pct, alpha_rain, a_corr):
    """Simula tutti i sensori e restituisce le previsioni in formato lungo, una
    riga per (sensore, giorno D, orizzonte h) con una previsione:

      sensore, periodo, data, orizzonte, data_target, umidita_prevista,
      e gli input del passo h: kc, ks, et0_prevista_mm, pioggia_prevista_mm,
      irrigazione_mm (registrata), efficacia
    """
    righe = []
    for _, p in periodi.iterrows():
        if p["sensore"] not in serie or p["coltura"] not in colture.index:
            continue
        righe += _simula_periodo(serie[p["sensore"]], p, colture.loc[p["coltura"]],
                                 mm_to_pct, alpha_rain, a_corr)
    return pd.DataFrame(righe)


def _simula_periodo(s, periodo, coltura, mm_to_pct, alpha_rain, a_corr):
    dentro = s["data"] >= periodo["installazione"]
    if pd.notna(periodo["rimozione"]):
        dentro &= s["data"] <= periodo["rimozione"]
    s = s[dentro].set_index("data")
    if s["umidita"].notna().sum() < 5:
        return []

    fc, wp, p = float(coltura["fc"]), float(coltura["wp"]), float(coltura["p"])
    kc = curva_kc(periodo["origine_kc"], coltura)
    # efficacia nominale del campo, zero se la sonda non vede l'irrigazione;
    # le irrigazioni fuori dal periodo non contano
    efficacia = float(periodo["efficacia"]) if periodo["irrigazione_visibile"] else 0.0
    irrigazione = s["irrigazione_mm"]

    righe = []
    for giorno, m0 in s["umidita"].dropna().items():
        m = float(m0)
        for h in ORIZZONTI:
            target = giorno + pd.Timedelta(days=h)
            kc_h = kc.get(target, np.nan)
            et0 = s.at[giorno, f"et0_prevista_t{h}"]
            pioggia = s.at[giorno, f"pioggia_prevista_t{h}"]
            if pd.isna(kc_h) or pd.isna(et0) or pd.isna(pioggia):
                break
            irr_mm = float(irrigazione.get(target, 0.0))

            ks = stress_idrico(m, fc, wp, p)
            etc_pct = ks * float(kc_h) * float(et0) * mm_to_pct
            pioggia_pct = alpha_rain * float(pioggia) * mm_to_pct
            irr_pct = a_corr * (irr_mm * efficacia) * mm_to_pct
            perc_pct = percolazione(m, fc)
            m = float(np.clip(m + pioggia_pct + irr_pct - etc_pct - perc_pct, wp, SATURAZIONE))

            righe.append({"sensore": periodo["sensore"], "periodo": periodo["periodo"],
                          "data": giorno, "orizzonte": h, "data_target": target,
                          "umidita_prevista": m, "kc": float(kc_h), "ks": ks,
                          "et0_prevista_mm": float(et0), "pioggia_prevista_mm": float(pioggia),
                          "irrigazione_mm": irr_mm, "efficacia": efficacia})
    return righe
