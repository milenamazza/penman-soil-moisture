"""
Serie giornaliere per sensore, sul calendario completo.

Ogni sensore ha una riga per ogni giorno di calendario fra la prima e l'ultima
umidità osservata, anche nei giorni in cui la sonda non ha trasmesso (lì
l'umidità è vuota). In questo modo la riga del giorno D+h corrisponde sempre
alla data D+h anche quando ci sono buchi nei dati, e le irrigazioni registrate
in giorni senza dati della sonda restano nella serie.

Colonne:
  data, umidita
  pioggia_prevista_t{h}, et0_prevista_t{h}   previsione emessa quel giorno per
                                             il giorno data + h (mm)
  pioggia_misurata_mm                        mediana fra le stazioni meteo
  irrigazione_mm                             mm registrati quel giorno
"""

import pandas as pd

from .config import MIN_GIORNI, ORIZZONTI


def costruisci_serie(umidita, previsioni, pioggia, irrigazioni):
    """{sensore: DataFrame} per i sensori con almeno MIN_GIORNI giorni con
    l'umidità osservata sia quel giorno sia il successivo."""
    # previsioni in formato largo: una riga per giorno di emissione
    larghe = previsioni.pivot_table(index="data_emissione", columns="orizzonte",
                                    values=["pioggia_mm", "et0_mm"], aggfunc="first")
    larghe.columns = [f"{'pioggia_prevista' if v == 'pioggia_mm' else 'et0_prevista'}_t{h}"
                      for v, h in larghe.columns]
    colonne_prev = [f"{v}_t{h}" for h in ORIZZONTI for v in ("pioggia_prevista", "et0_prevista")]
    larghe = larghe.reindex(columns=colonne_prev)
    pioggia = pioggia.set_index("data")["pioggia_misurata_mm"]

    serie = {}
    for sensore, u in umidita.groupby("sensore"):
        calendario = pd.date_range(u["data"].min(), u["data"].max(), freq="D")
        s = pd.DataFrame(index=calendario)
        s["umidita"] = u.set_index("data")["umidita"]
        s = s.join(larghe)
        s["pioggia_misurata_mm"] = pioggia.reindex(calendario).values
        irr = irrigazioni[irrigazioni["sensore"] == sensore].set_index("data")["irrigazione_mm"]
        s["irrigazione_mm"] = irr.reindex(calendario).fillna(0.0).values

        giorni_validi = (s["umidita"].notna() & s["umidita"].shift(-1).notna()).sum()
        if giorni_validi < MIN_GIORNI:
            continue
        serie[sensore] = s.rename_axis("data").reset_index()
    print(f"  serie pronte per {len(serie)} sensori")
    return serie
