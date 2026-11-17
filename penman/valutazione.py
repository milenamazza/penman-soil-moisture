"""
Confronto fra umidità prevista e osservata, e metriche di errore.

Non c'è uno split train/test: il bilancio idrico non ha parametri allenati sui
dati, quindi l'errore si calcola su tutti i giorni in cui esistono sia la
previsione sia l'umidità osservata.
"""

import numpy as np
import pandas as pd

from .config import ORIZZONTI


def aggiungi_osservato(previsioni, serie):
    """Aggiunge a ogni previsione l'umidità osservata nel giorno a cui si
    riferisce (data_target) e l'errore previsto - osservato."""
    osservato = pd.concat([s[["data", "umidita"]].assign(sensore=k) for k, s in serie.items()])
    osservato = osservato.rename(columns={"data": "data_target", "umidita": "umidita_osservata"})
    out = previsioni.merge(osservato, on=["sensore", "data_target"], how="left")
    out["errore"] = out["umidita_prevista"] - out["umidita_osservata"]
    return out


def metriche(previsioni, serie):
    """Per ogni orizzonte e su tutti insieme (ALL):

      n_osservati  coppie (giorno D, orizzonte h) con l'umidità osservata sia a
                   D sia a D+h, cioè dove una previsione si potrebbe valutare
      n            quante di queste hanno anche una previsione Penman
      MAE, RMSE, R2, bias (media di previsto - osservato; negativo = il
                   modello sta sotto)
    """
    possibili = {}
    for s in serie.values():
        u = s.set_index("data")["umidita"]
        for h in ORIZZONTI:
            dopo = u.reindex(u.index + pd.Timedelta(days=h)).to_numpy()
            possibili[h] = possibili.get(h, 0) + int((u.notna().to_numpy() & ~np.isnan(dopo)).sum())

    valutabili = previsioni.dropna(subset=["umidita_osservata"])
    gruppi = [(f"t+{h}", valutabili[valutabili["orizzonte"] == h], possibili[h]) for h in ORIZZONTI]
    gruppi.append(("ALL", valutabili, sum(possibili.values())))

    righe = []
    for etichetta, g, n_possibili in gruppi:
        oss, prev = g["umidita_osservata"].to_numpy(), g["umidita_prevista"].to_numpy()
        err = prev - oss
        righe.append({
            "orizzonte": etichetta, "n_osservati": n_possibili, "n": len(g),
            "MAE": round(float(np.mean(np.abs(err))), 4),
            "RMSE": round(float(np.sqrt(np.mean(err ** 2))), 4),
            "R2": round(float(1 - np.sum(err ** 2) / np.sum((oss - oss.mean()) ** 2)), 4),
            "bias": round(float(np.mean(err)), 4),
        })
    return pd.DataFrame(righe)
