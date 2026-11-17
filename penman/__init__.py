"""
Bilancio idrico Penman-Monteith (FAO-56) per prevedere l'umidità del suolo
misurata dalle sonde EM-500 da 1 a 7 giorni in avanti.

Moduli, nell'ordine in cui vengono usati:
  config       percorsi dei file e parametri del modello
  caricamento  lettura del dataset grezzo: umidità, pioggia delle stazioni,
               previsioni meteo
  anagrafica   colture (parametri FAO-56), periodi dei sensori, efficacia
               dell'irrigazione per campo, curva Kc
  serie        serie giornaliere per sensore, sul calendario completo
  bilancio     la fisica: stress idrico, percolazione, simulazione t+1..t+7
  valutazione  confronto con l'umidità osservata e metriche di errore
"""
