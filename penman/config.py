"""
Percorsi dei file di input e parametri del modello.

Tutti i file di input stanno in dati/, tranne il dataset grezzo
(dataset_pulito.csv, circa 1.7 GB), che non è incluso. Lo si può:
  - copiare in dati/dataset_pulito.csv;
  - indicare con --dataset a esegui_penman.py;
  - indicare con la variabile d'ambiente AI_AGRI_DATASET.
"""

import os

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATI = os.path.join(RADICE, "dati")
OUTPUT = os.path.join(RADICE, "output")

DATASET = os.environ.get("AI_AGRI_DATASET", os.path.join(DATI, "dataset_pulito.csv"))
SENSORI = os.path.join(DATI, "sensori.csv")        # periodi di installazione e colture
CAMPI = os.path.join(DATI, "campi.csv")            # sistema ed efficacia dell'irrigazione
IRRIGAZIONI = os.path.join(DATI, "irrigazioni.csv")  # registro delle irrigazioni
COLTURE = os.path.join(DATI, "colture.csv")        # parametri FAO-56 per coltura

# ── Parametri del modello ────────────────────────────────────────────────────
# Conversione da mm d'acqua a punti % di umidità volumetrica, la stessa per
# consumo (ETc), pioggia e irrigazione.
MM_TO_PCT = 0.2
# Efficacia della pioggia: frazione della pioggia che arriva alla sonda.
ALPHA_RAIN = 0.7
# Correzione che moltiplica l'efficacia nominale dell'irrigazione di ogni campo
# (cannone 0.60, ala piovana 0.85, da dati/campi.csv).
A_CORR = 1.0

# Orizzonti di previsione, in giorni.
ORIZZONTI = list(range(1, 8))
# Limite superiore dell'umidità simulata (% vol).
SATURAZIONE = 100.0
# Frazione giornaliera dell'eccesso sopra la capacità di campo che percola.
COEFF_PERCOLAZIONE = 0.05
# Un sensore entra nella simulazione solo se ha almeno questi giorni con
# l'umidità osservata sia oggi sia domani.
MIN_GIORNI = 20


def controlla_file(dataset):
    """Verifica che tutti i file di input esistano prima di leggere il dataset."""
    mancanti = [p for p in (dataset, SENSORI, CAMPI, IRRIGAZIONI, COLTURE)
                if not os.path.exists(p)]
    if mancanti:
        raise FileNotFoundError(
            "File di input mancanti:\n  " + "\n  ".join(mancanti)
            + "\nSe manca solo il dataset: copialo in dati/dataset_pulito.csv, oppure usa "
              "--dataset o la variabile d'ambiente AI_AGRI_DATASET.")
