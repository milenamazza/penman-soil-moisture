"""
grafici.py
─────────────────────────────────────────────────────────────────────────────
Grafici dei risultati di esegui_penman.py. Legge output/previsioni.csv,
output/metriche.csv e output/serie_giornaliere.csv e scrive in
output/grafici/:

  errore_per_orizzonte.png    MAE e RMSE per ogni orizzonte, da t+1 a t+7
  osservato_vs_previsto.png   umidità osservata contro prevista a t+1
  serie/<sensore>_<periodo>.png
                              una figura per sensore e periodo (coltura):
                              umidità osservata e prevista a t+1 nel tempo, e
                              sotto l'acqua in ingresso giorno per giorno

Ogni previsione è disegnata alla data a cui si riferisce (D+1).

    python grafici.py
    python grafici.py --risultati <cartella di output>
"""

import argparse
import os
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from penman import config  # noqa: E402

# Orizzonte mostrato nei grafici di dispersione e nelle serie.
ORIZZONTE = 1

# Colori. Il testo resta sempre in inchiostro neutro; i colori identificano le serie.
OSSERVATO = "#52514e"
PREVISTO = "#2a78d6"
INCHIOSTRO = "#0b0b0b"
INCHIOSTRO_2 = "#52514e"
GRIGLIA = "#e4e3df"
ACQUA = [  # (colonna, colore, etichetta) del pannello dell'acqua in ingresso
    ("pioggia_prevista_mm", "#6250d6", "pioggia prevista (usata dal modello)"),
    ("pioggia_misurata_mm", "#1baf7a", "pioggia misurata (stazioni)"),
    ("irrigazione_mm", "#eb6834", "irrigazione"),
]

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": INCHIOSTRO_2, "axes.labelcolor": INCHIOSTRO,
    "axes.titlecolor": INCHIOSTRO, "xtick.color": INCHIOSTRO_2, "ytick.color": INCHIOSTRO_2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRIGLIA, "grid.linewidth": 0.8, "legend.frameon": False,
    "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight",
    "axes.axisbelow": True,
})


def grafico_errore(metriche, percorso):
    """MAE e RMSE per orizzonte, con il valore scritto su ogni punto."""
    m = metriche[metriche["orizzonte"] != "ALL"].copy()
    m["h"] = m["orizzonte"].str[2:].astype(int)
    fig, assi = plt.subplots(1, 2, figsize=(11, 4.2))
    for asse, nome in zip(assi, ("MAE", "RMSE")):
        asse.plot(m["h"], m[nome], color=PREVISTO, linewidth=2, marker="o", markersize=6,
                  markeredgecolor="white")
        for _, r in m.iterrows():
            asse.annotate(f"{r[nome]:.2f}", (r["h"], r[nome]), textcoords="offset points",
                          xytext=(0, 8), ha="center", fontsize=8, color=INCHIOSTRO_2)
        asse.set_xticks(m["h"])
        asse.set_xticklabels([f"t+{h}" for h in m["h"]])
        asse.set_xlabel("orizzonte di previsione")
        asse.set_ylabel(f"{nome} (punti % di umidità)")
        asse.set_title(f"{nome} su tutti i giorni")
        asse.set_ylim(0, m[nome].max() * 1.15)
    fig.suptitle("Penman-Monteith: errore per orizzonte", fontsize=12, color=INCHIOSTRO)
    fig.savefig(percorso)
    plt.close(fig)


def grafico_dispersione(previsioni, percorso):
    """Umidità osservata contro prevista all'orizzonte ORIZZONTE."""
    d = previsioni[(previsioni["orizzonte"] == ORIZZONTE)].dropna(subset=["umidita_osservata"])
    valori = pd.concat([d["umidita_osservata"], d["umidita_prevista"]])
    lim = (valori.min() - 2, valori.max() + 2)
    fig, asse = plt.subplots(figsize=(5, 5))
    asse.plot(lim, lim, color=INCHIOSTRO_2, linewidth=1, linestyle="--", zorder=1)
    asse.scatter(d["umidita_osservata"], d["umidita_prevista"], s=10, color=PREVISTO,
                 alpha=0.3, edgecolor="none", zorder=2)
    mae = d["errore"].abs().mean()
    rmse = np.sqrt((d["errore"] ** 2).mean())
    asse.set_title(f"t+{ORIZZONTE}   MAE {mae:.2f}   RMSE {rmse:.2f}   n={len(d)}")
    asse.set_xlim(lim)
    asse.set_ylim(lim)
    asse.set_aspect("equal")
    asse.set_xlabel("umidità osservata (%)")
    asse.set_ylabel("umidità prevista (%)")
    fig.savefig(percorso)
    plt.close(fig)


def pannello_acqua(asse, giorni, colonne, larghezza=0.28):
    """Barre affiancate dei mm d'acqua in ingresso, una serie per tipo. L'asse
    verticale ha un massimo di almeno 10 mm, per una scala minima comune fra i
    grafici."""
    massimo = 0.0
    for k, (col, colore, etichetta) in enumerate(ACQUA):
        x = giorni + pd.to_timedelta((k - 1) * larghezza, unit="D")
        valori = colonne[col].fillna(0)
        asse.bar(x, valori, width=larghezza, color=colore, label=etichetta, linewidth=0)
        massimo = max(massimo, float(valori.max()))
    asse.set_ylabel("acqua (mm)")
    asse.set_ylim(0, max(10.0, massimo * 1.1))


def grafici_serie(previsioni, giornaliere, cartella):
    """Una figura per ogni sensore e periodo: umidità osservata e prevista
    all'orizzonte ORIZZONTE e, sotto, l'acqua in ingresso."""
    for (sensore, periodo), g in giornaliere[giornaliere["periodo"].notna()].groupby(["sensore", "periodo"]):
        p = previsioni[(previsioni["sensore"] == sensore) & (previsioni["periodo"] == periodo)
                       & (previsioni["orizzonte"] == ORIZZONTE)]
        if p.empty:
            continue
        fig, (a_um, a_acqua) = plt.subplots(2, 1, sharex=True, figsize=(12, 5.5),
                                            gridspec_kw={"height_ratios": [1.6, 1]})
        osservata = g.set_index("data")["umidita"]
        prevista = p.set_index("data_target")["umidita_prevista"].reindex(osservata.index)
        a_um.plot(osservata.index, osservata, color=OSSERVATO, linewidth=1.5, label="umidità osservata")
        a_um.plot(prevista.index, prevista, color=PREVISTO, linewidth=2,
                  label=f"umidità prevista a t+{ORIZZONTE}")
        a_um.set_title(f"t+{ORIZZONTE}   MAE {p['errore'].abs().mean():.2f}   giorni con "
                       f"previsione {p['errore'].notna().sum()}", loc="left", fontsize=10)
        a_um.set_ylabel("umidità (%)")
        a_um.legend(loc="lower right", bbox_to_anchor=(1, 1.0), ncol=2, fontsize=9)

        acqua = g.copy()
        acqua["irrigazione_mm"] = acqua["irrigazione_registrata_mm"].where(
            acqua["irrigazione_efficace_mm"] > 0, 0.0)
        pannello_acqua(a_acqua, acqua["data"], acqua)
        a_acqua.set_title("acqua in ingresso", loc="left", fontsize=10)
        a_acqua.legend(loc="lower right", bbox_to_anchor=(1, 1.0), ncol=3, fontsize=8)
        a_acqua.set_xlim(g["data"].min() - pd.Timedelta(days=1), g["data"].max() + pd.Timedelta(days=1))
        a_acqua.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%y"))

        coltura = g["coltura"].iloc[0]
        fig.suptitle(f"{sensore} - {coltura} dal {g['data'].min():%d/%m/%y} al {g['data'].max():%d/%m/%y}",
                     fontsize=12, color=INCHIOSTRO, x=0.01, ha="left")
        fig.savefig(os.path.join(cartella, f"{sensore}_{periodo}.png"))
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--risultati", default=config.OUTPUT, help="cartella di output di esegui_penman.py")
    args = parser.parse_args()

    previsioni = pd.read_csv(os.path.join(args.risultati, "previsioni.csv"),
                             parse_dates=["data", "data_target"])
    metriche = pd.read_csv(os.path.join(args.risultati, "metriche.csv"))
    giornaliere = pd.read_csv(os.path.join(args.risultati, "serie_giornaliere.csv"), parse_dates=["data"])

    cartella = os.path.join(args.risultati, "grafici")
    shutil.rmtree(cartella, ignore_errors=True)
    os.makedirs(os.path.join(cartella, "serie"))

    grafico_errore(metriche, os.path.join(cartella, "errore_per_orizzonte.png"))
    grafico_dispersione(previsioni, os.path.join(cartella, "osservato_vs_previsto.png"))
    grafici_serie(previsioni, giornaliere, os.path.join(cartella, "serie"))
    print(f"Grafici in {cartella}")


if __name__ == "__main__":
    main()
