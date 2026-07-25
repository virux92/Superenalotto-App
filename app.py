import streamlit as st
import pandas as pd
import numpy as np
import random
import math
from itertools import combinations

# Configurazione Pagina
st.set_page_config(page_title="SuperEnalotto AI & Sistemi", page_icon="🎰", layout="wide")

# --- DATASET INIZIALE REALE (ULTIME 50 ESTRAZIONI) ---
REAL_50_EXTRACTIONS = [
    {"concorso": "Conc. 118 (24/07)", "numeri": [20, 40, 53, 61, 74, 79], "superstar": 30},
    {"concorso": "Conc. 117 (23/07)", "numeri": [2, 12, 22, 34, 70, 74], "superstar": 8},
    {"concorso": "Conc. 116 (21/07)", "numeri": [13, 14, 15, 29, 38, 63], "superstar": 49},
    {"concorso": "Conc. 115 (18/07)", "numeri": [1, 28, 52, 62, 79, 86], "superstar": 31},
    {"concorso": "Conc. 114 (17/07)", "numeri": [7, 34, 45, 64, 65, 76], "superstar": 90},
    {"concorso": "Conc. 113 (16/07)", "numeri": [1, 15, 21, 46, 52, 67], "superstar": 76},
    {"concorso": "Conc. 112 (14/07)", "numeri": [8, 44, 49, 80, 85, 88], "superstar": 64},
    {"concorso": "Conc. 111 (11/07)", "numeri": [6, 7, 10, 47, 49, 61], "superstar": 62},
    {"concorso": "Conc. 110 (10/07)", "numeri": [2, 3, 12, 28, 63, 82], "superstar": 79},
    {"concorso": "Conc. 109 (09/07)", "numeri": [9, 17, 20, 31, 40, 79], "superstar": 47},
    {"concorso": "Conc. 108 (07/07)", "numeri": [3, 16, 30, 53, 55, 79], "superstar": 66},
    {"concorso": "Conc. 107 (04/07)", "numeri": [2, 37, 55, 62, 72, 76], "superstar": 75},
    {"concorso": "Conc. 106 (03/07)", "numeri": [22, 26, 30, 40, 68, 86], "superstar": 48},
    {"concorso": "Conc. 105 (02/07)", "numeri": [4, 17, 19, 23, 47, 59], "superstar": 82},
    {"concorso": "Conc. 104 (30/06)", "numeri": [1, 7, 51, 64, 78, 83], "superstar": 66},
    {"concorso": "Conc. 103 (27/06)", "numeri": [15, 19, 36, 47, 85, 90], "superstar": 62},
    {"concorso": "Conc. 102 (26/06)", "numeri": [1, 22, 30, 45, 73, 76], "superstar": 49},
    {"concorso": "Conc. 101 (25/06)", "numeri": [25, 27, 54, 72, 73, 76], "superstar": 80},
    {"concorso": "Conc. 100 (23/06)", "numeri": [1, 12, 17, 27, 66, 84], "superstar": 4},
    {"concorso": "Conc. 99 (20/06)", "numeri": [14, 59, 69, 71, 82, 89], "superstar": 3},
    {"concorso": "Conc. 98 (19/06)", "numeri": [14, 18, 25, 69, 81, 89], "superstar": 69},
    {"concorso": "Conc. 97 (18/06)", "numeri": [4, 26, 39, 43, 70, 87], "superstar": 57},
    {"concorso": "Conc. 96 (16/06)", "numeri": [4, 28, 33, 35, 66, 80], "superstar": 72},
    {"concorso": "Conc. 95 (13/06)", "numeri": [13, 23, 34, 68, 87, 90], "superstar": 54},
    {"concorso": "Conc. 94 (12/06)", "numeri": [18, 24, 42, 68, 75, 83], "superstar": 20},
    {"concorso": "Conc. 93 (11/06)", "numeri": [7, 21, 22, 40, 44, 87], "superstar": 83},
    {"concorso": "Conc. 92 (09/06)", "numeri": [18, 36, 47, 55, 73, 80], "superstar": 54},
    {"concorso": "Conc. 91 (08/06)", "numeri": [28, 33, 51, 59, 82, 87], "superstar": 87},
    {"concorso": "Conc. 90 (06/06)", "numeri": [2, 7, 29, 68, 72, 89], "superstar": 38},
    {"concorso": "Conc. 89 (05/06)", "numeri": [9, 25, 51, 63, 73, 89], "superstar": 40},
    {"concorso": "Conc. 88 (04/06)", "numeri": [12, 33, 43, 55, 74, 75], "superstar": 59},
    {"concorso": "Conc. 87 (30/05)", "numeri": [8, 13, 21, 39, 63, 71], "superstar": 56},
    {"concorso": "Conc. 86 (29/05)", "numeri": [9, 42, 44, 46, 85, 90], "superstar": 20},
    {"concorso": "Conc. 85 (28/05)", "numeri": [22, 33, 36, 74, 78, 86], "superstar": 34},
    {"concorso": "Conc. 84 (26/05)", "numeri": [7, 10, 35, 41, 45, 61], "superstar": 45},
    {"concorso": "Conc. 83 (23/05)", "numeri": [14, 29, 34, 57, 59, 69], "superstar": 16},
    {"concorso": "Conc. 82 (22/05)", "numeri": [5, 17, 65, 71, 83, 87], "superstar": 88},
    {"concorso": "Conc. 81 (21/05)", "numeri": [1, 38, 57, 58, 64, 81], "superstar": 50},
    {"concorso": "Conc. 80 (19/05)", "numeri": [49, 57, 61, 73, 79, 86], "superstar": 38},
    {"concorso": "Conc. 79 (16/05)", "numeri": [7, 12, 60, 69, 89, 90], "superstar": 36},
    {"concorso": "Conc. 78 (15/05)", "numeri": [5, 13, 17, 28, 47, 68], "superstar": 19},
    {"concorso": "Conc. 77 (14/05)", "numeri": [31, 56, 72, 74, 84, 85], "superstar": 34},
    {"concorso": "Conc. 76 (12/05)", "numeri": [2, 28, 31, 57, 58, 59], "superstar": 2},
    {"concorso": "Conc. 75 (09/05)", "numeri": [9, 27, 30, 42, 43, 62], "superstar": 11},
    {"concorso": "Conc. 74 (08/05)", "numeri": [8, 16, 41, 47, 51, 90], "superstar": 69},
    {"concorso": "Conc. 73 (07/05)", "numeri": [1, 34, 48, 66, 69, 73], "superstar": 58},
    {"concorso": "Conc. 72 (05/05)", "numeri": [24, 34, 45, 55, 81, 87], "superstar": 52},
    {"concorso": "Conc. 71 (04/05)", "numeri": [3, 14, 31, 46, 61, 63], "superstar": 24},
    {"concorso": "Conc. 70 (02/05)", "numeri": [7, 58, 60, 79, 84, 86], "superstar": 19},
    {"concorso": "Conc. 69 (30/04)", "numeri": [6, 7, 15, 44, 52, 58], "superstar": 16}
]

# --- INITIALIZATION DELLA SESSIONE (MEMORIA FIFO) ---
if "history" not in st.session_state:
    st.session_state.history = list(REAL_50_EXTRACTIONS)

def add_new_extraction(concorso, numeri, superstar):
    st.session_state.history.insert(0, {
        "concorso": concorso,
        "numeri": sorted(numeri),
        "superstar": superstar
    })
    if len(st.session_state.history) > 50:
        st.session_state.history.pop()

def get_best_superstar():
    ss_counts = {}
    for ext in st.session_state.history:
        ss = ext["superstar"]
        ss_counts[ss] = ss_counts.get(ss, 0) + 1
    return max(ss_counts, key=ss_counts.get) if ss_counts else random.randint(1, 90)

# --- CALCOLI STATISTICI AVANZATI ---
def calculate_metrics():
    history = st.session_state.history
    freq = {i: 0 for i in range(1, 91)}
    delay = {i: 50 for i in range(1, 91)}
    trend = {i: 0.0 for i in range(1, 91)}

    for k, ext in enumerate(history, start=1):
        for num in ext["numeri"]:
            freq[num] += 1
            if delay[num] == 50:
                delay[num] = k - 1
            trend[num] += 1.0 / math.sqrt(k)

    mu = 50 * (6 / 90)
    sigma = math.sqrt(50 * (6 / 90) * (1 - 6 / 90))
    z_scores = {i: (freq[i] - mu) / sigma for i in range(1, 91)}

    max_t = max(trend.values()) if max(trend.values()) > 0 else 1
    scores = {}
    for i in range(1, 91):
        scores[i] = (0.40 * z_scores[i]) + (0.30 * (delay[i] / 50.0)) + (0.30 * (trend[i] / max_t))

    return scores, freq, delay

def generate_optimized_sestina(scores):
    ranked = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    top_pool = ranked[:25]

    for _ in range(2000):
        sestina = sorted(random.sample(top_pool, 6))
        somma = sum(sestina)
        pari = sum(1 for x in sestina if x % 2 == 0)
        date_nums = sum(1 for x in sestina if x <= 31)

        if 200 <= somma <= 340 and pari in [2, 3, 4] and date_nums <= 4:
            best_ss = get_best_superstar()
            return sestina, best_ss, somma, f"{pari} Pari / {6-pari} Dispari"

    return ranked[:6], get_best_superstar(), sum(ranked[:6]), "3 Pari / 3 Dispari"

# --- GENERAZIONE SISTEMI STATISTICI ---
def generate_sistema_integrale(scores, n_numeri):
    ranked = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    selected_pool = sorted(ranked[:n_numeri])
    sestine = list(combinations(selected_pool, 6))
    return selected_pool, sestine

def generate_sistema_basi_varianti(scores, n_basi=2, n_varianti=8):
    ranked = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    basi = sorted(ranked[:n_basi])
    varianti_pool = ranked[n_basi:n_basi+n_varianti]
    
    k_var = 6 - n_basi
    var_combs = list(combinations(varianti_pool, k_var))
    
    sestine = []
    for vc in var_combs:
        sestina = sorted(list(basi) + list(vc))
        sestine.append(sestina)
        
    return basi, varianti_pool, sestine

def generate_sistema_ridotto_smart(scores, n_pool=12, max_sestine=8):
    ranked = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    top_pool = ranked[:n_pool]
    all_combs = list(combinations(top_pool, 6))
    
    filtered = []
    for c in all_combs:
        somma = sum(c)
        pari = sum(1 for x in c if x % 2 == 0)
        date_nums = sum(1 for x in c if x <= 31)
        if 200 <= somma <= 340 and pari in [2, 3, 4] and date_nums <= 4:
            filtered.append(sorted(c))
            
    if len(filtered) > max_sestine:
        selected_sestine = random.sample(filtered, max_sestine)
    else:
        selected_sestine = filtered if filtered else [sorted(c) for c in all_combs[:max_sestine]]
        
    return top_pool, selected_sestine

# --- INTERFACCIA GRAFICA STREAMLIT ---
st.title("🎰 SuperEnalotto AI — Predictor & Generatore Sistemi")
st.caption("Memoria fissa a 50 concorsi reali con gestione dinamica FIFO (First In, First Out).")

# Sidebar per la gestione dell'archivio
with st.sidebar:
    st.header("⚙️ Aggiungi Nuova Estrazione")
    st.info("La nuova estrazione entrerà in cima. Il concorso n° 50 (il più vecchio) verrà eliminato.")
    
    with st.form("add_form"):
        conc_name = st.text_input("Nome Concorso", value="Conc. Nuovo")
        col_a, col_b = st.columns(2)
        n1 = col_a.number_input("1° Num", 1, 90, 10)
        n2 = col_b.number_input("2° Num", 1, 90, 20)
        n3 = col_a.number_input("3° Num", 1, 90, 30)
        n4 = col_b.number_input("4° Num", 1, 90, 40)
        n5 = col_a.number_input("5° Num", 1, 90, 50)
        n6 = col_b.number_input("6° Num", 1, 90, 60)
        star = st.number_input("⭐ SuperStar", 1, 90, 15)
        
        submitted = st.form_submit_button("Aggiungi in Cima ed Elimina 50°")
        if submitted:
            new_nums = [n1, n2, n3, n4, n5, n6]
            if len(set(new_nums)) < 6:
                st.error("I 6 numeri devono essere tutti diversi!")
            else:
                add_new_extraction(conc_name, new_nums, star)
                st.success("Estrazione aggiunta! Il 50° concorso vecchio è stato rimosso.")

    if st.button("🔄 Ripristina i 50 Concorsi Reali Iniziali"):
        st.session_state.history = list(REAL_50_EXTRACTIONS)
        st.success("Memoria ripristinata ai 50 concorsi di base!")

scores, freq, delay = calculate_metrics()

# CREAZIONE TAB PRINCIPALI
tab_singola, tab_sistemi, tab_stats = st.tabs(["🎯 Sestina Singola", "🧩 Generatore Sistemi", "📊 Statistiche & Storico FIFO"])

with tab_singola:
    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.subheader("🎯 Previsione Sestina Singola")
        if st.button("🔮 Genera Nuova Sestina", type="primary", use_container_width=True):
            sestina, superstar, somma, bilancio = generate_optimized_sestina(scores)
            
            st.markdown("---")
            st.markdown("### 🌟 Combinazione Suggerita:")
            cols = st.columns(6)
            for idx, num in enumerate(sestina):
                cols[idx].metric(f"Num {idx+1}", str(num))
            
            st.metric("⭐ Numero SuperStar", str(superstar))
            
            st.markdown("**Dettagli Analitici Combinazione:**")
            st.write(f"- **Somma Totale:** {somma} (Range Ideale: 200-340)")
            st.write(f"- **Bilanciamento:** {bilancio}")
            st.markdown("---")
            
    with col_right:
        st.info("💡 L'algoritmo calcola i punteggi basandosi sugli ultimi 50 concorsi attivi nella tabella dello storico.")

with tab_sistemi:
    st.subheader("🧩 Generatore di Sistemi Statistici")
    st.write("Crea un sistema di gioco basato sui numeri top elaborati dall'algoritmo.")
    
    tipo_sistema = st.selectbox("Scegli la Tipologia di Sistema:", [
        "Sistema Integrale (Top 7, 8 o 9 Numeri)",
        "Sistema a Basi e Varianti (Fisse + Rotazione)",
        "Sistema Ridotto Smart (Filtro Statistico Ottimizzato)"
    ])
    
    best_ss = get_best_superstar()
    
    if tipo_sistema == "Sistema Integrale (Top 7, 8 o 9 Numeri)":
        n_num = st.radio("Numero di numeri nel sistema:", [7, 8, 9], horizontal=True)
        if st.button("🛠️ Genera Sistema Integrale", type="primary"):
            pool, sestine = generate_sistema_integrale(scores, n_num)
            st.success(f"Sistema Integrale sviluppato con successo! ({len(sestine)} Sestine)")
            
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                st.markdown(f"**Numeri Selezionati ({n_num}):** {', '.join(map(str, pool))}")
                st.markdown(f"**Costo Totale Stimato (1.25€/sestina con SS):** {len(sestine)*1.25:.2f} €")
            with col_s2:
                st.metric("⭐ SuperStar Consigliato per il Sistema", str(best_ss))
            
            df_sest = pd.DataFrame(sestine, columns=[f"N{i}" for i in range(1, 7)])
            df_sest["⭐ SuperStar"] = best_ss
            df_sest.index = [f"Sestina {i+1}" for i in range(len(sestine))]
            st.dataframe(df_sest, use_container_width=True)

    elif tipo_sistema == "Sistema a Basi e Varianti (Fisse + Rotazione)":
        col_b1, col_b2 = st.columns(2)
        n_b = col_b1.slider("Numero di Basi (Fisse top):", 1, 3, 2)
        n_v = col_b2.slider("Numero di Varianti:", 4, 10, 6)
        
        if st.button("🛠️ Genera Sistema Basi & Varianti", type="primary"):
            basi, varianti, sestine = generate_sistema_basi_varianti(scores, n_b, n_v)
            st.success(f"Sistema sviluppato con successo! ({len(sestine)} Sestine)")
            
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                st.markdown(f"**Basi Fisse (presenti in tutte le sestine):** {', '.join(map(str, basi))}")
                st.markdown(f"**Varianti in Rotazione:** {', '.join(map(str, varianti))}")
                st.markdown(f"**Costo Totale Stimato:** {len(sestine)*1.25:.2f} €")
            with col_s2:
                st.metric("⭐ SuperStar Consigliato per il Sistema", str(best_ss))
            
            df_sest = pd.DataFrame(sestine, columns=[f"N{i}" for i in range(1, 7)])
            df_sest["⭐ SuperStar"] = best_ss
            df_sest.index = [f"Sestina {i+1}" for i in range(len(sestine))]
            st.dataframe(df_sest, use_container_width=True)

    elif tipo_sistema == "Sistema Ridotto Smart (Filtro Statistico Ottimizzato)":
        col_r1, col_r2 = st.columns(2)
        pool_sz = col_r1.slider("Dimensione Pool Top Numeri:", 10, 15, 12)
        max_sest = col_r2.slider("Numero Massimo di Sestine desiderate:", 4, 12, 6)
        
        if st.button("🛠️ Genera Sistema Ridotto Smart", type="primary"):
            pool, sestine = generate_sistema_ridotto_smart(scores, pool_sz, max_sest)
            st.success(f"Sistema Ridotto Smart generato con successo! ({len(sestine)} Sestine)")
            
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                st.markdown(f"**Pool dei Top {pool_sz} Numeri Utilizzati:** {', '.join(map(str, sorted(pool)))}")
                st.markdown(f"**Costo Totale Stimato:** {len(sestine)*1.25:.2f} €")
            with col_s2:
                st.metric("⭐ SuperStar Consigliato per il Sistema", str(best_ss))
            
            df_sest = pd.DataFrame(sestine, columns=[f"N{i}" for i in range(1, 7)])
            df_sest["⭐ SuperStar"] = best_ss
            df_sest.index = [f"Sestina {i+1}" for i in range(len(sestine))]
            st.dataframe(df_sest, use_container_width=True)

with tab_stats:
    st.subheader("📊 Top Numeri Analizzati (su 50 concorsi attivi)")
    df_stats = pd.DataFrame({
        "Numero": list(range(1, 91)),
        "Frequenza": [freq[i] for i in range(1, 91)],
        "Ritardo": [delay[i] for i in range(1, 91)],
        "Score Algoritmo": [round(scores[i], 2) for i in range(1, 91)]
    }).sort_values(by="Score Algoritmo", ascending=False)
    
    st.dataframe(df_stats.head(15), use_container_width=True, hide_index=True)

    st.subheader("📜 Storico Memoria FIFO (Sempre 50 Concorsi Attivi)")
    st.caption("Il concorso in alto è il più recente. Il concorso in fondo (il 50°) verrà cancellato al prossimo inserimento.")
    history_df = pd.DataFrame([
        {
            "Posizione": f"N° {idx+1}",
            "Concorso": x["concorso"],
            "Sestina": ", ".join(map(str, x["numeri"])),
            "SuperStar": x["superstar"]
        } for idx, x in enumerate(st.session_state.history)
    ])
    st.dataframe(history_df, use_container_width=True, height=300)
