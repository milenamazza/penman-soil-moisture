"""
esegui_penman.py
─────────────────────────────────────────────────────────────────────────────
Previsione dell'umidità del suolo da t+1 a t+7 con il bilancio idrico
Penman-Monteith (FAO-56). Legge i dati, simula ogni sensore e salva
previsioni, metriche e serie giornaliere in output/.

    python esegui_penman.py
    python esegui_penman.py --dataset D:/dati/dataset_pulito.csv
    python esegui_penman.py --mm-to-pct 0.2 --alpha-rain 0.7 --a-corr 1.0

Output:
  previsioni.csv         una riga per (sensore, giorno D, orizzonte h): umidità
                         prevista e osservata a D+h, errore, e gli input usati
                         al passo h (Kc, Ks, ET0 e pioggia previste, irrigazione)
  metriche.csv           n, MAE, RMSE, R2 e bias per orizzonte e complessivi
  serie_giornaliere.csv  per sensore e giorno: periodo, umidità osservata,
                         pioggia prevista per quel giorno, pioggia misurata,
                         irrigazione registrata ed efficace
  periodi.csv            periodi dei sensori con l'efficacia dell'irrigazione
"""

import argparse
import os

import pandas as pd

from penman import config
from penman.anagrafica import carica_colture, carica_irrigazioni, carica_periodi
from penman.bilancio import simula
from penman.caricamento import carica_dataset
from penman.serie import costruisci_serie
from penman.valutazione import aggiungi_osservato, metriche


def serie_giornaliere(serie, periodi, a_corr):
    """Tabella giorno per giorno usata dai grafici: a ogni giorno il suo
    periodo, la pioggia prevista PER quel giorno (emessa il giorno prima) e
    l'irrigazione effettivamente usata dal modello."""
    pezzi = []
    for sensore, s in serie.items():
        t = s[["data", "umidita", "pioggia_misurata_mm", "irrigazione_mm"]].copy()
        t["pioggia_prevista_mm"] = s["pioggia_prevista_t1"].shift(1)
        t["sensore"] = sensore
        t["periodo"] = ""
        t["coltura"] = ""
        t["irrigazione_efficace_mm"] = 0.0
        for _, p in periodi[periodi["sensore"] == sensore].iterrows():
            dentro = t["data"] >= p["installazione"]
            if pd.notna(p["rimozione"]):
                dentro &= t["data"] <= p["rimozione"]
            t.loc[dentro, ["periodo", "coltura"]] = [p["periodo"], p["coltura"]]
            efficacia = p["efficacia"] if p["irrigazione_visibile"] else 0.0
            t.loc[dentro, "irrigazione_efficace_mm"] = t.loc[dentro, "irrigazione_mm"] * efficacia * a_corr
        pezzi.append(t)
    t = pd.concat(pezzi, ignore_index=True).rename(columns={"irrigazione_mm": "irrigazione_registrata_mm"})
    return t[["sensore", "data", "periodo", "coltura", "umidita", "pioggia_prevista_mm",
              "pioggia_misurata_mm", "irrigazione_registrata_mm", "irrigazione_efficace_mm"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[3])
    parser.add_argument("--dataset", default=config.DATASET)
    parser.add_argument("--out", default=config.OUTPUT)
    parser.add_argument("--mm-to-pct", type=float, default=config.MM_TO_PCT,
                        help="conversione mm -> punti %% di umidità (default %(default)s)")
    parser.add_argument("--alpha-rain", type=float, default=config.ALPHA_RAIN,
                        help="efficacia della pioggia (default %(default)s)")
    parser.add_argument("--a-corr", type=float, default=config.A_CORR,
                        help="correzione dell'efficacia nominale dell'irrigazione (default %(default)s)")
    args = parser.parse_args()

    config.controlla_file(args.dataset)
    os.makedirs(args.out, exist_ok=True)

    colture = carica_colture(config.COLTURE)
    periodi = carica_periodi(config.SENSORI, config.CAMPI)
    irrigazioni = carica_irrigazioni(config.IRRIGAZIONI)
    umidita, pioggia, previsioni_meteo = carica_dataset(args.dataset)
    serie = costruisci_serie(umidita, previsioni_meteo, pioggia, irrigazioni)

    print(f"Simulo (mm_to_pct={args.mm_to_pct:g}, alpha_rain={args.alpha_rain:g}, "
          f"a_corr={args.a_corr:g}) ...")
    previsioni = simula(serie, periodi, colture, args.mm_to_pct, args.alpha_rain, args.a_corr)
    previsioni = aggiungi_osservato(previsioni, serie)
    tabella = metriche(previsioni, serie)

    previsioni.round(4).to_csv(os.path.join(args.out, "previsioni.csv"), index=False)
    tabella.to_csv(os.path.join(args.out, "metriche.csv"), index=False)
    serie_giornaliere(serie, periodi, args.a_corr).round(4).to_csv(
        os.path.join(args.out, "serie_giornaliere.csv"), index=False)
    periodi.to_csv(os.path.join(args.out, "periodi.csv"), index=False)

    print("\nErrore (punti % di umidità):")
    print(tabella.to_string(index=False))
    print(f"\nRisultati in {args.out}")


if __name__ == "__main__":
    main()
