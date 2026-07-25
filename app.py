import streamlit as st
import pandas as pd
import numpy as np
import random
import math

# Configurazione Pagina
st.set_page_config(page_title="SuperEnalotto AI Predictor", page_icon="🎰", layout="wide")

# --- INITIALIZATION DELLA SESSIONE (MEMORIA FIFO 50) ---
if "history" not in st.session_state:
    # Generazione di 50 estrazioni iniziali di esempio
    initial_data = []
    for i in range(50, 0, -1):
        nums = sorted(random.sample(range(1, 91), 6))
        ss = random.randint(1, 90)
        initial_data.append({
            "concorso": f"Concorso {51-i}",
            "numeri": nums,
            "superstar": ss
        })
    st.session_state.history = initial_data

def add_new_extraction(concorso, numeri, superstar):
    # Aggiungi in testa e mantieni max 50 (FIFO)
    st.session_state.history.insert(0, {
        "concorso": concorso,
        "numeri": sorted(numeri),
        "superstar": superstar
    })
    if len(st.session_state.history) > 50:
        st.session_state.history.pop() # Rimuove l'ultimo (il 51°)

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

    # Z-Score Frequenza (Media teorica = 3.33 in 50 estrazioni, std = 1.76)
    mu = 50 * (6 / 90)
    sigma = math.sqrt(50 * (6 / 90) * (1 - 6 / 90))
    z_scores = {i: (freq[i] - mu) / sigma for i in range(1, 91)}

    # Normalizzazione Trend e Calcolo Score Finale
    max_t = max(trend.values()) if max(trend.values()) > 0 else 1
    scores = {}
    for i in range(1, 91):
        scores[i] = (0.40 * z_scores[i]) + (0.30 * (delay[i] / 50.0)) + (0.30 * (trend[i] / max_t))

    return scores, freq, delay

def generate_optimized_sestina(scores):
    ranked = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    top_pool = ranked[:25] # Prende i 25 numeri con score migliore

    # Tentativi di combinazione ottimale con filtri
    for _ in range(2000):
        sestina = sorted(random.sample(top_pool, 6))
        somma = sum(sestina)
        pari = sum(1 for x in sestina if x % 2 == 0)
        date_nums = sum(1 for x in sestina if x <= 31)

        # Filtri combinatori: Somma (200-340), Pari/Dispari (2/4, 3/3, 4/2), Max 4 numeri <= 31
        if 200 <= somma <= 340 and pari in [2, 3, 4] and date_nums <= 4:
            # Calcolo SuperStar basato su frequenza storica interna
            ss_counts = {}
            for ext in st.session_state.history:
                ss = ext["superstar"]
                ss_counts[ss] = ss_counts.get(ss, 0) + 1
            best_ss = max(ss_counts, key=ss_counts.get) if ss_counts else random.randint(1, 90)
            
            return sestina, best_ss, somma, f"{pari} Pari / {6-pari} Dispari"

    return ranked[:6], random.randint(1, 90), sum(ranked[:6]), "3 Pari / 3 Dispari"

# --- INTERFACCIA GRAFICA STREAMLIT ---
st.title("🎰 SuperEnalotto AI — Predictor & Memory FIFO")
st.caption("Sistema dinamico a finestra scorrevole sulle ultime 50 estrazioni.")

# Sidebar per la gestione dell'archivio
with st.sidebar:
    st.header("📥 Aggiungi Estrazione")
    st.info("La nuova estrazione spingerà fuori la più vecchia (Memoria fissa a 50).")
    
    with st.form("add_form"):
        conc_name = st.text_input("Nome/Numero Concorso", value="Concorso Nuovo")
        col_a, col_b = st.columns(2)
        n1 = col_a.number_input("1° Numero", 1, 90, 10)
        n2 = col_b.number_input("2° Numero", 1, 90, 20)
        n3 = col_a.number_input("3° Numero", 1, 90, 30)
        n4 = col_b.number_input("4° Numero", 1, 90, 40)
        n5 = col_a.number_input("5° Numero", 1, 90, 50)
        n6 = col_b.number_input("6° Numero", 1, 90, 60)
        star = st.number_input("⭐ SuperStar", 1, 90, 15)
        
        submitted = st.form_submit_button("Aggiungi ed Elimina Vecchia")
        if submitted:
            new_nums = [n1, n2, n3, n4, n5, n6]
            if len(set(new_nums)) < 6:
                st.error("I 6 numeri devono essere tutti diversi tra loro!")
            else:
                add_new_extraction(conc_name, new_nums, star)
                st.success("Dataset aggiornato con successo!")

# Contenuto Principale
col_left, col_right = st.columns([1, 1])

scores, freq, delay = calculate_metrics()

with col_left:
    st.subheader("🎯 Previsione Algoritmo")
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
    st.subheader("📊 Top Numeri Analizzati (su 50 concorsi)")
    df_stats = pd.DataFrame({
        "Numero": list(range(1, 91)),
        "Frequenza": [freq[i] for i in range(1, 91)],
        "Ritardo": [delay[i] for i in range(1, 91)],
        "Score Algoritmo": [round(scores[i], 2) for i in range(1, 91)]
    }).sort_values(by="Score Algoritmo", ascending=False)
    
    st.dataframe(df_stats.head(10), use_container_width=True, hide_index=True)

st.subheader("📜 Storico Memoria FIFO (Ultimi 50 Concorsi)")
history_df = pd.DataFrame([
    {
        "Concorso": x["concorso"],
        "Sestina": ", ".join(map(str, x["numeri"])),
        "SuperStar": x["superstar"]
    } for x in st.session_state.history
])
st.dataframe(history_df, use_container_width=True, height=250)
