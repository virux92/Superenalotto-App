from __future__ import annotations

from html import escape
from typing import Iterable

import streamlit as st


def apply_orion_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --orion-navy: #10152f;
            --orion-indigo: #4f46e5;
            --orion-violet: #7c3aed;
            --orion-cyan: #06b6d4;
            --orion-ink: #172033;
            --orion-muted: #64748b;
            --orion-border: rgba(79, 70, 229, 0.14);
            --orion-surface: rgba(255, 255, 255, 0.92);
        }

        .stApp {
            background:
                radial-gradient(circle at 8% 0%, rgba(99, 102, 241, 0.10), transparent 28rem),
                radial-gradient(circle at 96% 12%, rgba(6, 182, 212, 0.08), transparent 26rem),
                #f7f8fc;
        }

        [data-testid="stHeader"] { background: rgba(247, 248, 252, 0.72); }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #10152f 0%, #17143c 54%, #10152f 100%);
            border-right: 1px solid rgba(255,255,255,0.08);
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] [data-testid="stMetricValue"],
        [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
            color: #f8fafc !important;
        }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
            color: #cbd5e1 !important;
        }

        .block-container {
            max-width: 1420px;
            padding-top: 1.5rem;
            padding-bottom: 4rem;
        }

        div[data-testid="stMetric"] {
            background: var(--orion-surface);
            border: 1px solid var(--orion-border);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            box-shadow: 0 12px 32px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: var(--orion-ink);
            font-weight: 760;
        }

        /* Sidebar: contrasto alto e testo leggibile anche su schermi grandi. */
        [data-testid="stSidebar"] div[data-testid="stMetric"] {
            background: linear-gradient(
                135deg,
                rgba(255, 255, 255, 0.16),
                rgba(255, 255, 255, 0.08)
            ) !important;
            border: 1px solid rgba(255, 255, 255, 0.22) !important;
            border-radius: 14px;
            padding: .82rem .9rem;
            box-shadow: 0 10px 22px rgba(0, 0, 0, 0.16);
        }
        [data-testid="stSidebar"] div[data-testid="stMetric"] [data-testid="stMetricLabel"],
        [data-testid="stSidebar"] div[data-testid="stMetric"] [data-testid="stMetricLabel"] p {
            color: #cbd5e1 !important;
            font-size: .78rem !important;
            font-weight: 750 !important;
            line-height: 1.25 !important;
        }
        [data-testid="stSidebar"] div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #ffffff !important;
            font-size: 1.34rem !important;
            font-weight: 850 !important;
            line-height: 1.15 !important;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.28);
        }
        [data-testid="stSidebar"] p {
            font-size: .90rem;
            line-height: 1.55;
        }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
            color: #d8e0ec !important;
            font-size: .79rem !important;
            line-height: 1.45 !important;
        }
        [data-testid="stSidebar"] hr {
            border-color: rgba(255, 255, 255, 0.15) !important;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 14px;
            min-height: 2.9rem;
            font-weight: 700;
            border: 1px solid rgba(79, 70, 229, 0.22);
            transition: transform .14s ease, box-shadow .14s ease;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 24px rgba(79, 70, 229, 0.14);
        }
        .stButton > button[kind="primary"] {
            color: white;
            border: 0;
            background: linear-gradient(110deg, var(--orion-indigo), var(--orion-violet));
        }

        button[data-baseweb="tab"] {
            border-radius: 12px 12px 0 0;
            font-weight: 700;
        }

        .orion-hero {
            position: relative;
            overflow: hidden;
            padding: 1.7rem 1.8rem;
            border-radius: 24px;
            color: white;
            background:
                radial-gradient(circle at 84% 8%, rgba(34, 211, 238, .34), transparent 19rem),
                linear-gradient(120deg, #111936 0%, #312e81 52%, #6d28d9 100%);
            box-shadow: 0 24px 60px rgba(49, 46, 129, 0.22);
            margin-bottom: 1.15rem;
        }
        .orion-hero:after {
            content: "";
            position: absolute;
            width: 16rem;
            height: 16rem;
            right: -5rem;
            bottom: -9rem;
            border: 1px solid rgba(255,255,255,.20);
            border-radius: 999px;
            box-shadow: 0 0 0 2.5rem rgba(255,255,255,.035), 0 0 0 5rem rgba(255,255,255,.025);
        }
        .orion-eyebrow {
            display: inline-flex;
            align-items: center;
            gap: .45rem;
            font-size: .76rem;
            font-weight: 800;
            letter-spacing: .12em;
            text-transform: uppercase;
            color: #a5f3fc;
            margin-bottom: .55rem;
        }
        .orion-hero h1 {
            color: white;
            font-size: clamp(2rem, 4vw, 3.45rem);
            line-height: 1.02;
            margin: 0 0 .6rem 0;
            letter-spacing: -.045em;
        }
        .orion-hero p {
            max-width: 58rem;
            color: #e2e8f0;
            font-size: 1rem;
            margin: 0;
        }
        .orion-badge-row { display: flex; gap: .55rem; flex-wrap: wrap; margin-top: 1rem; }
        .orion-badge {
            display: inline-flex;
            padding: .38rem .68rem;
            border-radius: 999px;
            background: rgba(255,255,255,.12);
            border: 1px solid rgba(255,255,255,.16);
            color: white;
            font-size: .79rem;
            font-weight: 700;
            backdrop-filter: blur(8px);
        }

        .orion-panel {
            background: var(--orion-surface);
            border: 1px solid var(--orion-border);
            border-radius: 20px;
            padding: 1.2rem 1.25rem;
            box-shadow: 0 14px 36px rgba(15, 23, 42, 0.055);
            margin: .35rem 0 1rem 0;
        }
        .orion-panel-title {
            color: var(--orion-ink);
            font-size: 1rem;
            font-weight: 800;
            margin-bottom: .35rem;
        }
        .orion-panel-copy { color: var(--orion-muted); font-size: .92rem; line-height: 1.5; }

        .orion-ticket {
            background: linear-gradient(145deg, #ffffff, #f6f5ff);
            border: 1px solid rgba(99, 102, 241, .18);
            border-radius: 22px;
            padding: 1.25rem;
            box-shadow: 0 18px 42px rgba(49, 46, 129, .08);
            margin: .65rem 0 1rem 0;
        }
        .orion-ticket-label {
            color: #6366f1;
            font-size: .74rem;
            letter-spacing: .10em;
            text-transform: uppercase;
            font-weight: 850;
            margin-bottom: .75rem;
        }
        .orion-balls { display: flex; flex-wrap: wrap; align-items: center; gap: .72rem; }
        .orion-ball {
            width: 3.35rem;
            height: 3.35rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 999px;
            color: white;
            font-size: 1.22rem;
            font-weight: 850;
            background: linear-gradient(145deg, #4f46e5, #7c3aed);
            box-shadow: inset 0 1px 1px rgba(255,255,255,.38), 0 8px 18px rgba(79,70,229,.22);
        }
        .orion-ball.compact { width: 2.35rem; height: 2.35rem; font-size: .95rem; }
        .orion-plus { color: #94a3b8; font-weight: 800; padding: 0 .15rem; }
        .orion-superstar {
            min-width: 3.35rem;
            height: 3.35rem;
            padding: 0 .8rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: .35rem;
            border-radius: 999px;
            color: #3f2b00;
            font-size: 1.08rem;
            font-weight: 850;
            background: linear-gradient(145deg, #fde68a, #f59e0b);
            box-shadow: inset 0 1px 1px rgba(255,255,255,.55), 0 8px 18px rgba(245,158,11,.20);
        }
        .orion-superstar.compact { min-width: 2.35rem; height: 2.35rem; font-size: .88rem; padding: 0 .55rem; }

        .orion-chip-row { display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .65rem; }
        .orion-chip {
            display: inline-flex;
            align-items: center;
            gap: .3rem;
            padding: .34rem .58rem;
            border-radius: 999px;
            background: #eef2ff;
            color: #4338ca;
            border: 1px solid #dfe4ff;
            font-size: .82rem;
            font-weight: 750;
        }
        .orion-progress {
            height: .58rem;
            overflow: hidden;
            border-radius: 999px;
            background: #e8eaf4;
            margin-top: .55rem;
        }
        .orion-progress > span {
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, #4f46e5, #06b6d4);
        }
        .orion-disclaimer {
            color: #64748b;
            font-size: .78rem;
            line-height: 1.45;
            padding-top: .5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(version: str, status: str, signature: str) -> None:
    st.markdown(
        f"""
        <section class="orion-hero">
            <div class="orion-eyebrow">✦ Analisi automatica multi-memoria</div>
            <h1>ORION <span style="color:#a5f3fc">v{escape(version)}</span></h1>
            <p>Un’interfaccia semplice sopra un motore rigoroso: ORION analizza lo storico, fonde cinque memorie statistiche e costruisce la proposta senza scaricare sull’utente decine di parametri inutili.</p>
            <div class="orion-badge-row">
                <span class="orion-badge">Stato: {escape(status.title())}</span>
                <span class="orion-badge">Firma: {escape(signature)}</span>
                <span class="orion-badge">Nessuna previsione certa</span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def number_balls_html(
    numbers: Iterable[int],
    superstar: int | None = None,
    *,
    compact: bool = False,
    label: str = "Sestina ORION",
) -> str:
    size_class = " compact" if compact else ""
    balls = "".join(
        f'<span class="orion-ball{size_class}">{int(number)}</span>'
        for number in numbers
    )
    superstar_html = ""
    if superstar is not None:
        superstar_html = (
            '<span class="orion-plus">+</span>'
            f'<span class="orion-superstar{size_class}">★ {int(superstar)}</span>'
        )
    return (
        '<div class="orion-ticket">'
        f'<div class="orion-ticket-label">{escape(label)}</div>'
        f'<div class="orion-balls">{balls}{superstar_html}</div>'
        '</div>'
    )


def render_number_balls(
    numbers: Iterable[int],
    superstar: int | None = None,
    *,
    compact: bool = False,
    label: str = "Sestina ORION",
) -> None:
    st.markdown(
        number_balls_html(numbers, superstar, compact=compact, label=label),
        unsafe_allow_html=True,
    )


def render_chips(items: Iterable[str]) -> None:
    content = "".join(
        f'<span class="orion-chip">{escape(str(item))}</span>' for item in items
    )
    st.markdown(
        f'<div class="orion-chip-row">{content}</div>',
        unsafe_allow_html=True,
    )


def render_coherence(stability: float, label: str) -> None:
    percentage = max(0.0, min(1.0, float(stability))) * 100
    st.markdown(
        f"""
        <div class="orion-panel">
            <div class="orion-panel-title">Coerenza tra le memorie: {escape(label)}</div>
            <div class="orion-panel-copy">Misura quanto i segnali delle diverse finestre concordano tra loro. Non è una probabilità di vincita.</div>
            <div class="orion-progress"><span style="width:{percentage:.1f}%"></span></div>
            <div class="orion-disclaimer">Indice interno: {percentage:.1f}/100</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
