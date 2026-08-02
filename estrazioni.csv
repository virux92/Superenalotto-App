from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.analytics import archive_analytics
from core.backtest import records_tuple, run_walk_forward_backtest as engine_backtest
from core.combinations import (
    combination_features,
    euro,
    generate_base_variant_system,
    generate_integral_system,
    generate_reduced_system,
    rank_candidate_sestine,
    system_cost,
)
from core.metrics import calculate_metrics, calculate_superstar_ranking
from database import (
    delete_recommendation,
    fetch_draws,
    fetch_recommendations,
    save_recommendation,
)
from services.archive_service import archive_snapshot, load_primary_archive
from services.draw_service import dataframe_to_history
from services.recommendation_service import (
    build_monitoring_tables,
    suggest_next_target,
)
from services.forge_service import build_forge_snapshot
from services.orion_service import build_orion_snapshot
from services.presentation_service import build_candidate_profile, build_orion_brief
from ui.orion_ui import (
    apply_orion_theme,
    render_chips,
    render_coherence,
    render_hero,
    render_number_balls,
)

APP_TITLE = "ORION v2.7.3 — SuperEnalotto Quant Engine"
DATA_FILE = Path(__file__).with_name("estrazioni.csv")

st.set_page_config(page_title=APP_TITLE, page_icon="🌌", layout="wide")


@st.cache_data(show_spinner=False)
def rank_candidate_sestine_cached(
    score_items: tuple[tuple[int, float], ...],
    top_pool_size: int,
    limit: int,
    minimum_sum: int,
    maximum_sum: int,
    maximum_low_numbers: int,
    minimum_decades: int,
) -> list[tuple[float, tuple[int, ...]]]:
    return rank_candidate_sestine(
        dict(score_items),
        top_pool_size,
        limit,
        minimum_sum,
        maximum_sum,
        maximum_low_numbers,
        minimum_decades,
    )


@st.cache_data(show_spinner=False)
def run_walk_forward_backtest_cached(
    raw_records: tuple[tuple[Any, ...], ...],
    window_size: int,
    test_limit: int,
    pool_size: int,
    minimum_sum: int,
    maximum_sum: int,
    maximum_low_numbers: int,
    minimum_decades: int,
    random_seed: int,
) -> dict[str, Any]:
    return engine_backtest(
        raw_records,
        window_size,
        test_limit,
        pool_size,
        minimum_sum,
        maximum_sum,
        maximum_low_numbers,
        minimum_decades,
        random_seed,
    )


@st.cache_data(show_spinner=False)
def archive_analytics_cached(
    raw_records: tuple[tuple[Any, ...], ...], association_limit: int
) -> dict[str, Any]:
    dataframe = pd.DataFrame(
        raw_records,
        columns=[
            "data", "anno", "concorso", "n1", "n2", "n3", "n4", "n5", "n6", "jolly", "superstar"
        ],
    )
    dataframe["data"] = pd.to_datetime(dataframe["data"])
    dataframe["jolly"] = pd.to_numeric(dataframe["jolly"]).mask(lambda values: values.eq(0)).astype("Int64")
    return archive_analytics(dataframe_to_history(dataframe), association_limit)


@st.cache_data(show_spinner=False, ttl=3600)
def build_forge_snapshot_cached(
    raw_records: tuple[tuple[Any, ...], ...],
) -> dict[str, Any]:
    dataframe = pd.DataFrame(
        raw_records,
        columns=[
            "data", "anno", "concorso", "n1", "n2", "n3", "n4", "n5", "n6", "jolly", "superstar"
        ],
    )
    dataframe["data"] = pd.to_datetime(dataframe["data"])
    dataframe["jolly"] = (
        pd.to_numeric(dataframe["jolly"])
        .mask(lambda values: values.eq(0))
        .astype("Int64")
    )
    return build_forge_snapshot(dataframe)


def initialize_state() -> None:
    if "single_result" not in st.session_state:
        st.session_state.single_result = None
    if "orion_candidate_index" not in st.session_state:
        st.session_state.orion_candidate_index = 0
    if "system_result" not in st.session_state:
        st.session_state.system_result = None
    if "backtest_result" not in st.session_state:
        st.session_state.backtest_result = None


def render_sidebar(
    archive: pd.DataFrame,
    orion: dict[str, Any],
    archive_source: str,
) -> str:
    latest = archive.sort_values(["data", "concorso"]).iloc[-1]
    brief = build_orion_brief(orion)

    st.sidebar.markdown("## ✦ ORION")
    st.sidebar.caption("Quant Engine · modalità automatica")
    navigation = st.sidebar.radio(
        "Navigazione",
        ["Home", "Genera", "Schedine", "Archivio", "Impostazioni"],
        key="orion_navigation",
        label_visibility="collapsed",
    )
    st.sidebar.divider()
    st.sidebar.metric("Archivio", f"{len(archive):,}".replace(",", "."))
    st.sidebar.metric("Ultimo concorso", f"{int(latest['concorso'])}/{int(latest['anno'])}")
    st.sidebar.metric("Coerenza", brief["coherence"])
    st.sidebar.caption(
        f"Dati: {archive_source} · aggiornati al {pd.Timestamp(latest['data']):%d/%m/%Y}"
    )
    st.sidebar.divider()
    st.sidebar.markdown(
        "ORION e FORGE lavorano automaticamente. L’utente vede soltanto le funzioni "
        "necessarie per generare, salvare e controllare le schedine."
    )
    st.sidebar.caption(
        "Il SuperEnalotto resta un gioco casuale. Il motore ordina dati e criteri; "
        "non crea probabilità aggiuntiva."
    )
    return str(navigation)


def render_single_tab(
    orion: dict[str, Any],
    archive: pd.DataFrame,
    database_available: bool,
) -> None:
    candidates = orion["candidates"]
    brief = build_orion_brief(orion)

    if st.session_state.single_result is None:
        quality, combo = candidates[0]
        st.session_state.orion_candidate_index = 0
        st.session_state.single_result = {
            "combo": combo,
            "quality": quality,
            "profile": build_candidate_profile(combo, orion),
            "superstar": orion["superstar_ranking"][0][0],
            "signature": orion["signature"],
        }

    title_column, action_column = st.columns([1.55, 1])
    with title_column:
        st.subheader("Il consiglio di ORION")
        st.caption(
            "La proposta principale è deterministica: a parità di archivio e modello, "
            "ORION restituisce la stessa sestina."
        )
    with action_column:
        action_columns = st.columns(2)
        reset_main = action_columns[0].button(
            "Proposta principale", type="primary", use_container_width=True
        )
        next_alternative = action_columns[1].button(
            "Altra proposta", use_container_width=True
        )

    if reset_main:
        st.session_state.orion_candidate_index = 0
    elif next_alternative:
        candidate_count = min(30, len(candidates))
        st.session_state.orion_candidate_index = (
            int(st.session_state.orion_candidate_index) + 1
        ) % candidate_count

    selected_index = int(st.session_state.orion_candidate_index)
    quality, combo = candidates[selected_index]
    current_combo = tuple(st.session_state.single_result["combo"])
    if combo != current_combo or reset_main or next_alternative:
        st.session_state.single_result = {
            "combo": combo,
            "quality": quality,
            "profile": build_candidate_profile(combo, orion),
            "superstar": orion["superstar_ranking"][0][0],
            "signature": orion["signature"],
        }

    result = st.session_state.single_result
    profile = result["profile"]
    proposal_label = (
        "Proposta principale"
        if selected_index == 0
        else f"Alternativa ORION #{selected_index}"
    )
    render_number_balls(
        result["combo"],
        int(result["superstar"]),
        label=proposal_label,
    )

    detail_columns = st.columns(4)
    detail_columns[0].metric("Somma", profile["features"]["sum"])
    even = profile["features"]["even"]
    detail_columns[1].metric("Pari / dispari", f"{even} / {6-even}")
    detail_columns[2].metric("Decine coperte", profile["features"]["decades"])
    detail_columns[3].metric("Numeri nella top 12", profile["top_twelve_count"])

    explanation_column, coherence_column = st.columns([1.5, 1])
    with explanation_column:
        st.markdown("#### Perché è stata scelta")
        structural_text = (
            "rispetta tutti i vincoli strutturali ricavati dall’archivio"
            if profile["structural_ok"]
            else "usa il miglior compromesso disponibile tra punteggio e struttura"
        )
        st.markdown(
            f"- **Consenso medio:** {profile['average_score']:.1%} sullo score normalizzato.\n"
            f"- **Accordo tra memorie:** {profile['average_agreement']:.1%}.\n"
            f"- **Struttura:** {structural_text}.\n"
            f"- **Posizionamento:** numeri compresi tra il {profile['best_rank']}° e il "
            f"{profile['worst_rank']}° posto del ranking corrente."
        )
    with coherence_column:
        render_coherence(float(orion["stability"]), brief["coherence"])

    with st.expander("Salva e monitora questa schedina", expanded=False):
        if not database_available:
            st.warning(
                "Il salvataggio persistente richiede Supabase. In questo momento "
                "l’app sta leggendo il CSV di emergenza."
            )
        else:
            default_year, default_contest = suggest_next_target(archive)
            with st.form("save_generated_recommendation"):
                save_columns = st.columns([1.4, 1, 1, 1])
                name = save_columns[0].text_input(
                    "Nome",
                    value=f"ORION {pd.Timestamp.now():%d/%m/%Y}",
                )
                start_year = save_columns[1].number_input(
                    "Anno iniziale", min_value=2020, max_value=2100,
                    value=int(default_year), step=1,
                )
                start_contest = save_columns[2].number_input(
                    "Concorso iniziale", min_value=1,
                    value=int(default_contest), step=1,
                )
                draw_count = save_columns[3].number_input(
                    "Concorsi", min_value=1, max_value=100,
                    value=5, step=1,
                )
                notes = st.text_input(
                    "Note facoltative",
                    placeholder="Esempio: stessa sestina per 5 concorsi",
                )
                save_submitted = st.form_submit_button(
                    "Salva nel monitoraggio", type="primary", use_container_width=True
                )
            if save_submitted:
                try:
                    saved = save_recommendation(
                        list(result["combo"]),
                        int(result["superstar"]),
                        int(start_year),
                        int(start_contest),
                        int(draw_count),
                        name=name,
                        source="orion_v2_7",
                        notes=notes,
                    )
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success(
                        f"Schedina #{saved['id']} salvata. Gli esiti verranno aggiornati "
                        "quando saranno disponibili le nuove estrazioni."
                    )

    st.divider()
    watch_column, latest_column = st.columns(2)
    with watch_column:
        st.markdown("#### Numeri sotto osservazione")
        st.caption(
            "Sono i numeri con il consenso ORION più alto adesso. Non sono numeri “più probabili”."
        )
        render_chips([str(number) for number in brief["top_numbers"]])
        st.caption(
            "Memorie attive: " + " · ".join(brief["memories"])
        )
    with latest_column:
        latest = archive.sort_values(["data", "concorso"]).iloc[-1]
        latest_numbers = [int(latest[f"n{index}"]) for index in range(1, 7)]
        st.markdown("#### Ultima estrazione acquisita")
        st.caption(
            f"Concorso {int(latest['concorso'])}/{int(latest['anno'])} · "
            f"{pd.Timestamp(latest['data']):%d/%m/%Y} · Jolly "
            f"{('—' if pd.isna(latest['jolly']) else int(latest['jolly']))}"
        )
        render_number_balls(
            latest_numbers,
            int(latest["superstar"]),
            compact=True,
            label="Numeri estratti",
        )

    st.caption(
        "ORION applica criteri statistici allo storico, ma ogni sestina conserva la stessa "
        "probabilità matematica di qualunque altra sestina valida."
    )


def render_systems_tab(
    scores: dict[int, float], superstar_ranking: list[tuple[int, float, int, int]]
) -> None:
    st.subheader("Crea un sistema ORION")
    st.caption(
        "Scegli soltanto il livello di spesa. ORION seleziona automaticamente "
        "i numeri e costruisce le sestine."
    )

    profile_specs = {
        "Compatto · 8 sestine": {
            "lines": 8,
            "description": "Spesa contenuta e sestine diversificate.",
        },
        "Equilibrato · 15 sestine": {
            "lines": 15,
            "description": "Due numeri base e sei varianti combinate.",
        },
        "Integrale 7 numeri · 7 sestine": {
            "lines": 7,
            "description": "Tutte le sestine ottenibili da un gruppo di 7 numeri.",
        },
    }

    selection_column, option_column = st.columns([1.55, 1])
    with selection_column:
        system_profile = st.radio(
            "Tipo di sistema",
            list(profile_specs),
            key="orion_system_profile",
        )
        st.caption(str(profile_specs[system_profile]["description"]))
    with option_column:
        with_superstar = st.toggle(
            "Aggiungi SuperStar a tutte le sestine",
            value=True,
            key="orion_system_superstar",
        )
        line_count = int(profile_specs[system_profile]["lines"])
        st.metric("Costo previsto", euro(system_cost(line_count, with_superstar)))
        st.caption(
            f"{line_count} sestine · tariffa configurata: 1,00 € ciascuna"
            + (" + 0,50 € SuperStar" if with_superstar else "")
        )

    if st.button(
        "Genera sistema ORION",
        type="primary",
        use_container_width=True,
        key="generate_orion_system",
    ):
        coverage = None
        bases: list[int] = []
        variants: list[int] = []

        if system_profile == "Compatto · 8 sestine":
            pool, lines, coverage = generate_reduced_system(scores, 12, 8)
            method = "Compatto"
        elif system_profile == "Equilibrato · 15 sestine":
            bases, variants, lines = generate_base_variant_system(scores, 2, 6)
            pool = sorted([*bases, *variants])
            method = "Equilibrato"
        else:
            pool, lines = generate_integral_system(scores, 7)
            method = "Integrale 7 numeri"

        st.session_state.system_result = {
            "profile": system_profile,
            "method": method,
            "pool": pool,
            "bases": bases,
            "variants": variants,
            "lines": lines,
            "coverage": coverage,
            "with_superstar": with_superstar,
            "superstar": superstar_ranking[0][0],
        }

    result = st.session_state.system_result
    if not result:
        return

    lines = result["lines"]
    st.divider()
    st.markdown("#### Sistema generato")
    summary_columns = st.columns(4)
    summary_columns[0].metric("Profilo", result["method"])
    summary_columns[1].metric("Numeri usati", len(result["pool"]))
    summary_columns[2].metric("Sestine", len(lines))
    summary_columns[3].metric(
        "Costo totale", euro(system_cost(len(lines), result["with_superstar"]))
    )

    if result["bases"]:
        st.markdown("**Numeri base:** " + " · ".join(map(str, result["bases"])))
        st.markdown("**Numeri variabili:** " + " · ".join(map(str, result["variants"])))
    else:
        st.markdown("**Numeri scelti da ORION:**")
        render_chips([str(number) for number in result["pool"]])

    system_dataframe = pd.DataFrame(
        lines, columns=[f"N{index}" for index in range(1, 7)]
    )
    if result["with_superstar"]:
        system_dataframe["SuperStar"] = int(result["superstar"])
    st.dataframe(system_dataframe, use_container_width=True, hide_index=True, height=480)
    st.download_button(
        "Scarica sistema CSV",
        system_dataframe.to_csv(index=False).encode("utf-8-sig"),
        "sistema_orion_v2_7_3.csv",
        "text/csv",
        use_container_width=True,
    )
    st.caption(
        "Il costo mostrato dipende dal numero di sestine e dall’eventuale SuperStar. "
        "Più sestine aumentano la copertura acquistata, non la capacità di prevedere l’estrazione."
    )


def render_generate_view(
    orion: dict[str, Any],
    archive: pd.DataFrame,
    database_available: bool,
) -> None:
    render_hero(orion["version"], orion["status"], orion["signature"])
    proposal_tab, system_tab = st.tabs(["Proposta singola", "Sistema"])
    with proposal_tab:
        render_single_tab(orion, archive, database_available)
    with system_tab:
        render_systems_tab(orion["score"], orion["superstar_ranking"])

def render_statistics_tab(
    active_dataframe: pd.DataFrame,
    metrics: dict[str, dict[int, float]],
    scores: dict[int, float],
    superstar_ranking: list[tuple[int, float, int, int]],
) -> None:
    ranking_tab, structure_tab, association_tab, stability_tab = st.tabs(
        ["Ranking numeri", "Struttura estrazioni", "Coppie e terzine", "Stabilità annuale"]
    )

    analytics = archive_analytics_cached(records_tuple(active_dataframe), 100)

    with ranking_tab:
        stats_dataframe = pd.DataFrame(
            {
                "Numero": range(1, 91),
                "Frequenza": [
                    int(metrics["frequency"][number]) for number in range(1, 91)
                ],
                "Ritardo": [
                    int(metrics["delay"][number]) for number in range(1, 91)
                ],
                "Recenza": [
                    round(metrics["recency"][number], 4) for number in range(1, 91)
                ],
                "Score": [round(scores[number], 4) for number in range(1, 91)],
            }
        ).sort_values(["Score", "Numero"], ascending=[False, True])
        st.dataframe(stats_dataframe, use_container_width=True, hide_index=True, height=520)

        st.subheader("Ranking SuperStar")
        superstar_dataframe = pd.DataFrame(
            [
                {
                    "Numero": number,
                    "Score": round(score, 4),
                    "Frequenza": frequency,
                    "Ritardo": delay,
                }
                for number, score, frequency, delay in superstar_ranking[:20]
            ]
        )
        st.dataframe(superstar_dataframe, use_container_width=True, hide_index=True)

    with structure_tab:
        st.caption(
            "Analisi descrittiva della finestra attiva. Gli scostamenti storici "
            "non costituiscono una previsione delle estrazioni future."
        )
        summary_dataframe = pd.DataFrame(analytics["structure_summary"])
        st.dataframe(summary_dataframe, use_container_width=True, hide_index=True)

        decade_dataframe = pd.DataFrame(analytics["decades"])
        st.subheader("Distribuzione per decine")
        st.bar_chart(decade_dataframe.set_index("Decina")["Presenze"])
        st.dataframe(decade_dataframe, use_container_width=True, hide_index=True)

        st.subheader("Ripetizioni rispetto all'estrazione precedente")
        overlap_dataframe = pd.DataFrame(analytics["overlaps"])
        st.dataframe(overlap_dataframe, use_container_width=True, hide_index=True)

        with st.expander("Dettaglio strutturale delle estrazioni"):
            structure_dataframe = pd.DataFrame(analytics["structure_rows"])
            structure_dataframe["Entropia decine"] = structure_dataframe[
                "Entropia decine"
            ].round(4)
            st.dataframe(
                structure_dataframe.sort_values(["Anno", "Concorso"], ascending=False),
                use_container_width=True,
                hide_index=True,
                height=520,
            )

    with association_tab:
        association_limit = st.slider("Associazioni da mostrare", 10, 100, 30, 10)
        st.caption(
            "Le coppie e le terzine sono ordinate per presenze nella finestra. "
            "L'atteso casuale si riferisce a una specifica associazione fissata in anticipo; "
            "la selezione delle più frequenti è retrospettiva."
        )
        pairs = pd.DataFrame(analytics["pairs"]).head(association_limit)
        triplets = pd.DataFrame(analytics["triplets"]).head(association_limit)
        pair_column, triplet_column = st.columns(2)
        with pair_column:
            st.subheader("Coppie più presenti")
            st.dataframe(pairs, use_container_width=True, hide_index=True, height=520)
        with triplet_column:
            st.subheader("Terzine più presenti")
            st.dataframe(triplets, use_container_width=True, hide_index=True, height=520)

    with stability_tab:
        stability_dataframe = pd.DataFrame(analytics["annual_stability"])
        display_mode = st.radio(
            "Ordinamento",
            ["Più stabili", "Più variabili", "Numero"],
            horizontal=True,
        )
        if display_mode == "Più stabili":
            stability_dataframe = stability_dataframe.sort_values(
                ["Stabilità", "Numero"], ascending=[False, True]
            )
        elif display_mode == "Più variabili":
            stability_dataframe = stability_dataframe.sort_values(
                ["CV", "Numero"], ascending=[False, True]
            )
        else:
            stability_dataframe = stability_dataframe.sort_values("Numero")
        st.caption(
            "Il tasso annuale è la quota di estrazioni dell'anno in cui il numero è comparso. "
            "CV basso indica maggiore uniformità storica, non maggiore probabilità futura."
        )
        st.dataframe(
            stability_dataframe,
            use_container_width=True,
            hide_index=True,
            height=600,
        )


def render_backtest_tab(archive: pd.DataFrame) -> None:
    st.subheader("Backtest walk-forward sull'archivio")
    st.write(
        "Ogni estrazione viene simulata usando soltanto le estrazioni precedenti "
        "contenute nella finestra mobile selezionata."
    )

    backtest_columns = st.columns(5)
    backtest_window = backtest_columns[0].selectbox("Finestra", [50, 100, 200], index=1)
    backtest_pool = backtest_columns[1].selectbox(
        "Pool algoritmo", [15, 16, 17, 18], index=0
    )
    test_choice = backtest_columns[2].selectbox(
        "Numero test", ["Ultimi 100", "Ultimi 300", "Tutti"], index=1
    )
    test_limit = {"Ultimi 100": 100, "Ultimi 300": 300, "Tutti": 0}[test_choice]
    minimum_decades_backtest = backtest_columns[3].selectbox(
        "Min decine", [3, 4], index=0
    )
    random_seed = backtest_columns[4].number_input(
        "Seed casuale", min_value=0, value=20260726, step=1
    )

    st.caption(
        "Filtri backtest: somma 190–350, massimo 4 numeri fino a 31. "
        "Il benchmark casuale è deterministico e riproducibile tramite il seed."
    )

    if st.button("Esegui backtest", type="primary"):
        with st.spinner("Calcolo storico in corso..."):
            st.session_state.backtest_result = run_walk_forward_backtest_cached(
                records_tuple(archive),
                int(backtest_window),
                int(test_limit),
                int(backtest_pool),
                190,
                350,
                4,
                int(minimum_decades_backtest),
                int(random_seed),
            )

    backtest = st.session_state.backtest_result
    if backtest:
        top_metrics = st.columns(3)
        top_metrics[0].metric("Test eseguiti", backtest["test_count"])
        top_metrics[1].metric("Seed benchmark", backtest["random_seed"])
        top_metrics[2].metric(
            "2+ casuali teorici attesi", f"{backtest['random_expected_2_plus']:.2f}"
        )

        summary_dataframe = pd.DataFrame(backtest["summary"])
        numeric_columns = [
            "Media punti", "Deviazione", "IC95% minimo", "IC95% massimo"
        ]
        summary_dataframe[numeric_columns] = summary_dataframe[numeric_columns].round(4)
        st.dataframe(summary_dataframe, use_container_width=True, hide_index=True)

        st.caption(
            "Riferimento teorico casuale: media 0,400 punti per sestina. "
            "L'intervallo di confidenza descrive l'incertezza della media osservata."
        )

        with st.expander("Stabilità annuale del backtest"):
            annual_dataframe = pd.DataFrame(backtest["annual_summary"])
            annual_dataframe["Media punti"] = annual_dataframe["Media punti"].round(4)
            st.dataframe(annual_dataframe, use_container_width=True, hide_index=True)

        detail_dataframe = pd.DataFrame(backtest["details"])
        st.dataframe(
            detail_dataframe.tail(300),
            use_container_width=True,
            hide_index=True,
            height=520,
        )
        st.download_button(
            "Scarica dettaglio backtest",
            detail_dataframe.to_csv(index=False).encode("utf-8-sig"),
            "backtest_superenalotto.csv",
            "text/csv",
        )


def render_monitored_tickets_tab(
    archive: pd.DataFrame, database_available: bool
) -> None:
    st.subheader("Schedine consigliate e risultati")
    st.caption(
        "Ogni schedina viene confrontata automaticamente con i concorsi indicati. "
        "Quando aggiungi una nuova estrazione a Supabase, il relativo esito compare qui."
    )

    if not database_available:
        st.warning(
            "Il monitoraggio persistente richiede Supabase. L'archivio è attualmente "
            "caricato dal CSV di emergenza."
        )
        return

    default_year, default_contest = suggest_next_target(archive)
    with st.expander("Registra una schedina già giocata", expanded=False):
        # Questo controllo resta fuori dal form: i widget contenuti in un form
        # aggiornano lo stato soltanto al submit. In questo modo la selezione
        # abilita immediatamente il campo numerico del SuperStar.
        has_superstar = st.checkbox(
            "SuperStar giocato",
            value=False,
            key="manual_has_superstar",
            help="Attiva il campo per indicare il numero SuperStar effettivamente giocato.",
        )

        with st.form("manual_recommendation"):
            identity_columns = st.columns(4)
            name = identity_columns[0].text_input(
                "Nome", value="Schedina giocata", key="manual_ticket_name"
            )
            start_year = identity_columns[1].number_input(
                "Anno iniziale", min_value=2020, max_value=2100,
                value=int(default_year), step=1, key="manual_start_year",
            )
            start_contest = identity_columns[2].number_input(
                "Concorso iniziale", min_value=1, value=int(default_contest),
                step=1, key="manual_start_contest",
            )
            draw_count = identity_columns[3].number_input(
                "Concorsi giocati", min_value=1, max_value=100, value=5,
                step=1, key="manual_draw_count",
            )

            number_columns = st.columns(6)
            numbers = [
                number_columns[index - 1].number_input(
                    f"N{index}", min_value=1, max_value=90, value=index,
                    step=1, key=f"manual_ticket_n{index}",
                )
                for index in range(1, 7)
            ]
            superstar = st.number_input(
                "Numero SuperStar",
                min_value=1,
                max_value=90,
                value=1,
                step=1,
                disabled=not has_superstar,
                key="manual_ticket_superstar",
                help=(
                    "Numero SuperStar associato alla schedina. "
                    "Il campo si abilita selezionando ‘SuperStar giocato’ sopra il modulo."
                ),
            )
            notes = st.text_input(
                "Note facoltative", key="manual_ticket_notes",
                placeholder="Esempio: stessa schedina per cinque concorsi",
            )
            submitted = st.form_submit_button(
                "Registra e monitora", type="primary", use_container_width=True
            )
        if submitted:
            try:
                saved = save_recommendation(
                    [int(number) for number in numbers],
                    int(superstar) if has_superstar else None,
                    int(start_year),
                    int(start_contest),
                    int(draw_count),
                    name=name,
                    source="inserimento_manuale",
                    notes=notes,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.session_state["ticket_flash"] = (
                    f"Schedina #{saved['id']} registrata correttamente."
                )
                st.rerun()

    flash = st.session_state.pop("ticket_flash", None)
    if flash:
        st.success(flash)

    try:
        recommendations = fetch_recommendations()
    except Exception as exc:
        st.error(f"Impossibile leggere le schedine monitorate: {exc}")
        return

    if recommendations.empty:
        st.info(
            "Non ci sono ancora schedine monitorate. Puoi salvare una sestina generata "
            "oppure registrare qui una schedina già giocata."
        )
        return

    summary, details = build_monitoring_tables(recommendations, archive)
    total_results = int(summary["Risultati 2+"].sum()) if not summary.empty else 0
    evaluated_draws = int(summary["Concorsi valutati"].sum()) if not summary.empty else 0
    pending_draws = int(summary["Concorsi in attesa"].sum()) if not summary.empty else 0
    metric_columns = st.columns(4)
    metric_columns[0].metric("Schedine monitorate", len(summary))
    metric_columns[1].metric("Concorsi valutati", evaluated_draws)
    metric_columns[2].metric("Risultati da 2 in su", total_results)
    metric_columns[3].metric("Concorsi in attesa", pending_draws)

    st.subheader("Riepilogo schedine")
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("Esito di ogni estrazione")
    if details.empty:
        st.info("I concorsi iniziali registrati non sono ancora presenti nell'archivio.")
    else:
        display_details = details.copy()
        display_details["Segnalazione"] = display_details.apply(
            lambda row: (
                f"✅ {row['Risultato']}"
                if int(row["Punti"]) >= 2
                else f"— {row['Risultato']}"
            ),
            axis=1,
        )
        display_details["Data"] = pd.to_datetime(display_details["Data"]).dt.strftime(
            "%d/%m/%Y"
        )
        preferred_columns = [
            "Segnalazione", "Nome", "Data", "Concorso", "Sestina giocata",
            "Numeri estratti", "Punti", "Numeri centrati", "Jolly centrato",
            "SuperStar centrato",
        ]
        st.dataframe(
            display_details[preferred_columns],
            use_container_width=True,
            hide_index=True,
            height=520,
        )
        st.download_button(
            "Scarica storico risultati CSV",
            details.to_csv(index=False).encode("utf-8-sig"),
            "storico_schedine_monitorate.csv",
            "text/csv",
        )

    with st.expander("Elimina una schedina dal monitoraggio"):
        ticket_options = {
            f"#{int(row.id)} — {row.nome} — {int(row.concorso_inizio)}/{int(row.anno_inizio)}": int(row.id)
            for row in recommendations.itertuples(index=False)
        }
        selected_label = st.selectbox(
            "Schedina", list(ticket_options), key="delete_ticket_selection"
        )
        selected_id = ticket_options[selected_label]
        confirmation = st.text_input(
            f"Per confermare scrivi ELIMINA {selected_id}",
            key="delete_ticket_confirmation",
        )
        if st.button(
            "Elimina schedina",
            disabled=confirmation.strip() != f"ELIMINA {selected_id}",
            key="delete_monitored_ticket",
        ):
            try:
                delete_recommendation(selected_id)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.session_state["ticket_flash"] = (
                    f"Schedina #{selected_id} eliminata dal monitoraggio."
                )
                st.rerun()


def render_archive_tab(archive: pd.DataFrame) -> None:
    st.subheader("Archivio completo")
    year_options = ["Tutti"] + sorted(archive["anno"].unique().tolist(), reverse=True)
    selected_year = st.selectbox("Anno", year_options)

    display_archive = archive.copy()
    if selected_year != "Tutti":
        display_archive = display_archive[display_archive["anno"] == int(selected_year)]

    display_archive = display_archive.sort_values("data", ascending=False)
    display_archive["data"] = display_archive["data"].dt.strftime("%d/%m/%Y")
    display_archive["jolly"] = display_archive["jolly"].astype("Int64")
    st.dataframe(display_archive, use_container_width=True, hide_index=True, height=600)


def render_data_and_verification_tab(
    archive: pd.DataFrame,
    metrics: dict[str, dict[int, float]],
    scores: dict[int, float],
    superstar_ranking: list[tuple[int, float, int, int]],
) -> None:
    st.subheader("Dati e verifica")
    st.caption(
        "Qui restano disponibili gli strumenti tecnici. Sono separati dalla schermata "
        "principale perché servono a controllare il motore, non a pilotarlo a mano."
    )
    archive_tab, statistics_tab, backtest_tab = st.tabs(
        ["Archivio", "Statistiche", "Backtest"]
    )
    with archive_tab:
        render_archive_tab(archive)
    with statistics_tab:
        render_statistics_tab(archive.copy(), metrics, scores, superstar_ranking)
    with backtest_tab:
        render_backtest_tab(archive)


def render_home_view(
    archive: pd.DataFrame,
    orion: dict[str, Any],
    forge: dict[str, Any],
    archive_source: str,
    database_error: str | None,
) -> None:
    render_hero(orion["version"], orion["status"], orion["signature"])
    latest = archive.sort_values(["data", "concorso"]).iloc[-1]
    brief = build_orion_brief(orion)

    metric_columns = st.columns(4)
    metric_columns[0].metric(
        "Ultimo concorso", f"{int(latest['concorso'])}/{int(latest['anno'])}"
    )
    metric_columns[1].metric("Archivio", f"{len(archive):,}".replace(",", "."))
    metric_columns[2].metric(
        "Modello attivo", str(orion.get("model_id", "ORION-BALANCED"))
    )
    metric_columns[3].metric("Stato", "Stabile" if forge["state"] == "stable" else "Protetto")

    st.caption(
        f"Fonte dati: **{archive_source}** · archivio aggiornato al "
        f"{pd.Timestamp(latest['data']):%d/%m/%Y} · coerenza {brief['coherence'].lower()}."
    )
    if database_error and archive_source != "Supabase":
        st.warning("Supabase non è disponibile: ORION sta usando il CSV di sicurezza.")

    primary = tuple(orion["primary"])
    superstar = int(orion["superstar_ranking"][0][0])
    st.subheader("Ultima proposta ORION")
    render_number_balls(primary, superstar, label="Proposta principale")

    def open_generate() -> None:
        st.session_state["orion_navigation"] = "Genera"

    st.button(
        "Genera nuova proposta",
        type="primary",
        use_container_width=True,
        on_click=open_generate,
    )


def render_settings_view(
    archive: pd.DataFrame,
    forge: dict[str, Any],
    archive_source: str,
    database_error: str | None,
) -> None:
    st.subheader("Impostazioni")
    st.caption(
        "ORION è configurato per funzionare in automatico. Non ci sono pesi, finestre "
        "o filtri statistici da regolare manualmente."
    )

    active = forge.get("active_model")
    columns = st.columns(4)
    columns[0].metric("Fonte dati", archive_source)
    columns[1].metric("FORGE", "Attivo")
    columns[2].metric("Candidati validi", int(forge.get("valid_count", 0)))
    columns[3].metric(
        "Modello", str(active.get("model_id")) if active else "Profilo protetto"
    )

    st.markdown("#### Automazione")
    st.markdown(
        "- FORGE crea e confronta i modelli candidati senza intervento manuale.\n"
        "- Gli esperimenti già respinti o falliti sullo stesso archivio non vengono ripetuti.\n"
        "- ORION riceve soltanto modelli che hanno superato i controlli operativi.\n"
        "- Se nessun candidato supera i controlli, resta attivo il profilo bilanciato protetto."
    )

    st.markdown("#### Archivio")
    latest = archive.sort_values(["data", "concorso"]).iloc[-1]
    archive_count = f"{len(archive):,}".replace(",", ".")
    st.write(
        f"{archive_count} estrazioni disponibili, aggiornate al "
        f"{pd.Timestamp(latest['data']):%d/%m/%Y}."
    )
    if database_error:
        st.info("La connessione principale non è disponibile; il CSV locale resta operativo.")

    with st.expander("Stato tecnico di FORGE", expanded=False):
        st.json(
            {
                "stato": forge.get("state"),
                "registro": forge.get("registry"),
                "candidati": forge.get("candidate_count"),
                "validi": forge.get("valid_count"),
                "respinti": forge.get("rejected_count"),
                "falliti": forge.get("failed_count"),
                "esperimenti_saltati_perche_gia_noti": forge.get("skipped_known"),
            }
        )


def main() -> None:
    apply_orion_theme()
    try:
        repository_archive, archive_source, database_error = load_primary_archive(
            str(DATA_FILE), fetch_draws
        )
    except (FileNotFoundError, ValueError, pd.errors.ParserError) as exc:
        st.error(str(exc))
        st.stop()

    initialize_state()
    archive = repository_archive
    with st.spinner("FORGE verifica i modelli disponibili..."):
        forge = build_forge_snapshot_cached(records_tuple(archive))
    orion = build_orion_snapshot(archive, forge)
    database_available = archive_source == "Supabase" and database_error is None

    navigation = render_sidebar(archive, orion, archive_source)
    if navigation == "Home":
        render_home_view(archive, orion, forge, archive_source, database_error)
    elif navigation == "Genera":
        render_generate_view(orion, archive, database_available)
    elif navigation == "Schedine":
        render_monitored_tickets_tab(archive, database_available)
    elif navigation == "Archivio":
        render_archive_tab(archive)
    else:
        render_settings_view(archive, forge, archive_source, database_error)


if __name__ == "__main__":
    main()
