# views.py — Monitor de Bolsa TAG (ETFs): seções do app (visão geral, estratégia, top 10, look-through).
# Dados: tag_equities.json, gerado por build_tag_equities.py (Morningstar MCP).
# =============================================================================
import json
import os

import plotly.graph_objects as go
import streamlit as st

_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tag_equities.json")

TAG_VINHO = "#630d24"
TAG_LARANJA = "#FF8853"
TAG_GREEN = "#1A7A42"
TAG_RED = "#B00020"
TAG_GRAY = "#6A6864"
ETF_COLORS = {"CSPX": "#630D24", "CIBR": "#5C85F7", "BKCH": "#FFBB00", "BRIJ": "#477C88",
              "SOXQ": "#FF8853", "DRAM": "#A485F2", "GRDU": "#6BDE97"}

_TH = "padding:7px 9px;text-align:center;font-weight:600;white-space:nowrap"
_TD = "padding:6px 9px;text-align:center;white-space:nowrap"


# ===================== FORMATADORES (PT-BR) =====================
def _num(v, d=2, suffix=""):
    if v is None:
        return "—"
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".") + suffix


def _pct(v, d=2):
    return _num(v, d, "%")


def _ret(v, d=2):
    """Retorno colorido (verde/vermelho)."""
    if v is None:
        return f"<span style='color:{TAG_GRAY}'>—</span>"
    c = TAG_GREEN if v >= 0 else TAG_RED
    return f"<span style='color:{c};font-weight:600'>{_pct(v, d)}</span>"


def _pp(v, d=1):
    """Diferença em pontos percentuais, colorida."""
    if v is None:
        return f"<span style='color:{TAG_GRAY}'>—</span>"
    c = TAG_GREEN if v >= 0 else TAG_RED
    return f"<span style='color:{c};font-weight:600'>{'+' if v >= 0 else ''}{_num(v, d)} p.p.</span>"


def _mult(v, d=1):
    return "—" if v is None else _num(v, d, "x")


def _bn(v):
    if v is None:
        return "—"
    if v >= 1000:
        return "US$ " + _num(v / 1000, 2) + " tri"
    return "US$ " + _num(v, 1) + " bi"


def _pfv(v):
    if v is None:
        return "—"
    c = TAG_GREEN if v < 0.95 else (TAG_RED if v > 1.05 else TAG_GRAY)
    return f"<span style='color:{c};font-weight:600'>{_num(v, 2)}</span>"


def _moat(m):
    if not m:
        return "—"
    colors = {"Wide": TAG_GREEN, "Narrow": "#9A6E00", "None": TAG_GRAY}
    c = colors.get(m, TAG_GRAY)
    return f"<span style='color:{c};border:1px solid {c}55;padding:0 6px;border-radius:8px;font-size:11px'>{m}</span>"


def _pill(key):
    c = ETF_COLORS.get(key, TAG_GRAY)
    return (f"<span style='background:{c};color:#fff;padding:1px 7px;border-radius:8px;"
            f"font-size:11px;font-weight:700'>{key}</span>")


def _table(headers, rows, min_width=900, first_left=True):
    head = "".join(
        f"<th style='{_TH};{'text-align:left' if (i == 0 and first_left) else ''}'>{h}</th>"
        for i, h in enumerate(headers))
    body = ""
    for r in rows:
        style = r.get("_style", "")
        cells = "".join(
            f"<td style='{_TD};{'text-align:left' if (i == 0 and first_left) else ''}'>{c}</td>"
            for i, c in enumerate(r["cells"]))
        body += f"<tr style='border-bottom:1px solid #eee;{style}'>{cells}</tr>"
    st.markdown(f"""
    <div style="border-radius:10px;overflow:hidden;border:1px solid rgba(99,13,36,0.12);overflow-x:auto">
    <table style="width:100%;border-collapse:collapse;font-size:12.5px;background:#fff;min-width:{min_width}px">
        <thead style="background:{TAG_VINHO};color:#fff"><tr>{head}</tr></thead>
        <tbody>{body}</tbody>
    </table></div>""", unsafe_allow_html=True)


def _section(title):
    st.markdown(f"<p class='section-title' style='font-weight:700;color:{TAG_VINHO};font-size:1.05rem;"
                f"margin:22px 0 8px 0'>{title}</p>", unsafe_allow_html=True)


def _kpi(label, value, sub=""):
    return (f"<div style='background:#fff;border:1px solid rgba(99,13,36,0.15);border-radius:10px;"
            f"padding:8px 10px;min-width:0;flex:1 1 0'>"
            f"<div style='font-size:11px;color:{TAG_GRAY};text-transform:uppercase;letter-spacing:.4px'>{label}</div>"
            f"<div style='font-size:1.15rem;font-weight:700;color:{TAG_VINHO}'>{value}</div>"
            f"<div style='font-size:11px;color:{TAG_GRAY}'>{sub}</div></div>")


def _br_date(iso):
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


@st.cache_data(show_spinner=False)
def _load():
    with open(_DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_data():
    return _load()


def render_header_note():
    data = _load()
    ref = _br_date(data["reference_date"])
    mo_end = _br_date(data["mo_end_date"])
    st.markdown(
        "<p style='font-size:0.85rem;color:#666;margin-bottom:0.8rem'>"
        "Carteira de bolsa TAG — 7 ETFs com foco no ecossistema de IA (compute, memória, energia, "
        "segurança, infraestrutura e cripto/HPC) sobre um núcleo de S&P 500. Dados Morningstar (MCP). "
        f"📅 Preços e retornos diários até <b>{ref}</b>; retornos 24M/36M e vol 12M com fechamento "
        f"mensal de <b>{mo_end}</b>; holdings de <b>{_br_date(data['holdings_date'])}</b>.</p>",
        unsafe_allow_html=True,
    )


# ===================== VISÃO GERAL =====================
def render_overview():
    data = _load()
    etfs, port, xray = data["etfs"], data["portfolio"], data["xray"]
    mo_end = _br_date(data["mo_end_date"])

    # ── KPIs da carteira ──
    kpis = "".join([
        _kpi("Retorno dia", _pct(port["r1d"]), "média ponderada"),
        _kpi("MTD", _pct(port["mtd"]), f"desde {mo_end}"),
        _kpi("YTD", _pct(port["ytd"]), f"{_num(port['ytd_cov'], 0)}% da carteira c/ dado"),
        _kpi("12 meses", _pct(port["r1y"]), f"{_num(port['r1y_cov'], 0)}% da carteira c/ dado"),
        _kpi("P/E TTM", _mult(port["pe"]), f"X-Ray: {_mult(xray['price_ratios']['portfolio']['pe'])}"),
        _kpi("P/E Fwd", _mult(port["fpe"]), "lucro projetado"),
        _kpi("P/BV", _mult(port["pb"], 2), f"X-Ray: {_mult(xray['price_ratios']['portfolio']['pb'], 2)}"),
        _kpi("ROE", _pct(port["roe"], 1), f"X-Ray: {_pct(xray['profitability']['portfolio']['roe'], 1)}"),
        _kpi("Div. Yield", _pct(port["dy"]), "trailing 12m"),
    ])
    st.markdown(f"<div style='display:flex;gap:6px;overflow-x:auto'>{kpis}</div>", unsafe_allow_html=True)

    # ── Alocação ──
    _section("🧩 Alocação e camada do ecossistema")
    c1, c2 = st.columns([1, 1.4])
    with c1:
        fig = go.Figure(go.Pie(
            labels=[e["key"] for e in etfs], values=[e["weight"] for e in etfs], hole=0.55,
            marker=dict(colors=[ETF_COLORS[e["key"]] for e in etfs], line=dict(color="#fff", width=2)),
            sort=False, textinfo="label+percent", textfont=dict(size=12),
            hovertemplate="%{label}: %{value:.1f}%<extra></extra>",
        ))
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
                          paper_bgcolor="rgba(0,0,0,0)",
                          annotations=[dict(text="Bolsa<br>TAG", showarrow=False, font=dict(size=14, color=TAG_VINHO))])
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        _table(["ETF", "Peso", "Camada do ecossistema", "Taxa"],
               [{"cells": [_pill(e["key"]), _pct(e["weight"], 1), e["camada"], _pct(e["ter"])]} for e in etfs],
               min_width=420)

    # ── Performance ──
    _section("📈 Preço, tamanho e retornos")
    rows = []
    for e in etfs:
        vol = _pct(e["vol1y"])
        if e.get("vol_note"):
            vol += "<sup>*</sup>"
        r1y = _ret(e["r1y"])
        if e["r1y"] is None and e.get("since_inception") is not None:
            r1y = f"{_ret(e['since_inception'])}<sup>†</sup>"
        rows.append({"cells": [
            f"{_pill(e['key'])} <span style='color:{TAG_GRAY};font-size:11px'>{e['listing']}</span>",
            _pct(e["weight"], 1), f"{e['cur']} {_num(e['price'])}", _bn(e["aum_usd_bn"]),
            _bn(e["avg_mcap_usd_bn"]), _ret(e["r1d"]), _ret(e["mtd"]), _ret(e["ytd"]), r1y,
            _ret(e["r2y"]), _ret(e["r3y"]), vol,
        ]})
    rows.append({"_style": f"background:{TAG_VINHO}0d;font-weight:700", "cells": [
        "<b>Carteira TAG</b>", "100%", "—", "—", "—", _ret(port["r1d"]), _ret(port["mtd"]),
        _ret(port["ytd"]), _ret(port["r1y"]), _ret(port["r2y"]), _ret(port["r3y"]), "—"]})
    _table(["ETF", "Peso", "Preço", "AUM", "Mkt cap médio", "Dia", "MTD", "YTD", "12M",
            "24M a.a.", "36M a.a.", "Vol 12M"], rows, min_width=1100)
    st.caption(
        "Mkt cap médio = média geométrica do valor de mercado das ações do ETF (Morningstar). "
        "24M/36M anualizados. Carteira = média dos ETFs pelos pesos atuais, renormalizada para os ETFs com "
        "dado no período (DRAM só existe desde 01/04/2026; BRIJ desde 03/09/2024). "
        "† DRAM: retorno desde o início (01/04/2026). * DRAM: vol anualizada desde o início.")

    # ── Retorno desde a entrada de cada tema na carteira ──
    _section("🎯 Retorno desde a entrada de cada tema na carteira TAG")
    from datetime import date
    ref_d = date.fromisoformat(data["reference_date"])
    erows = []
    for e in sorted([e for e in etfs if e.get("entry_date")], key=lambda e: e["entry_date"]):
        days = (ref_d - date.fromisoformat(e["entry_date"])).days
        erows.append({"cells": [
            _pill(e["key"]), e["camada"], _pct(e["weight"], 1), _br_date(e["entry_date"]), _num(days, 0),
            _ret(e["since_entry"]), _ret(e["cspx_since_entry"]), _pp(e["since_entry"] - e["cspx_since_entry"]),
        ]})
    _table(["Tema", "Camada", "Peso", "Entrada", "Dias", "Retorno desde a entrada", "CSPX no período",
            "Diferença vs. CSPX"], erows, min_width=900)
    st.caption(
        "Retorno total em USD do fechamento da data de entrada até "
        f"{_br_date(data['reference_date'])} (Daily Return Index Morningstar). CSPX no período = S&P 500 (núcleo "
        "da carteira) entre as mesmas datas; diferença em pontos percentuais. Períodos curtos, sem anualizar.")

    # ── Retorno por ano-calendário + USD/BRL ──
    _section("📅 Retorno por ano-calendário (USD) e variação cambial")
    cal = data["calendar"]
    years = [str(y) for y in cal["years"]]
    head = [f"{y} (YTD)" if y == years[0] else y for y in years]
    crows = []
    for r in cal["rows"]:
        cells = [_pill(r["key"]), _pct(r["weight"], 1)]
        for y in years:
            v = _ret(r["returns"][y])
            if r["flags"].get(y) and r["returns"][y] is not None:
                v += "<sup>†</sup>"
            cells.append(v)
        crows.append({"cells": cells})
    crows.append({"_style": f"background:{TAG_VINHO}0d;font-weight:700", "cells":
                  ["<b>Carteira TAG (USD)</b>", "100%"] + [_ret(cal["portfolio"][y]) for y in years]})
    crows.append({"_style": "background:#f7f7f7;border-top:2px solid #ddd", "cells":
                  ["<b>USD/BRL</b> <span style='color:#888;font-size:11px'>(PTAX)</span>", "—"]
                  + [_ret(cal["usdbrl"][y]) for y in years]})
    crows.append({"_style": "background:#f7f7f7;font-weight:700", "cells":
                  ["<b>Carteira TAG em BRL</b>", "—"] + [_ret(cal["portfolio_brl"][y]) for y in years]})
    _table(["ETF", "Peso"] + head, crows, min_width=760)
    lv = cal["usdbrl_levels"]
    cov_txt = " · ".join(f"{y}: {_num(cal['portfolio_cov'][y], 0)}%" for y in years)
    st.caption(
        f"Retorno total em USD. {years[0]} = acumulado no ano até {_br_date(data['reference_date'])}. "
        "Em branco: ETF ainda não existia ou teve ano parcial de lançamento (BRIJ 03/09/2024, GRDU 14/04/2022). "
        "† DRAM: desde o início (01/04/2026), fora da média da carteira. Carteira = média pelos pesos atuais, "
        f"renormalizada para os ETFs com ano completo (cobertura — {cov_txt}). "
        "USD/BRL = variação da PTAX venda do Banco Central entre fins de ano "
        f"(R$ {_num(lv['2021'], 4)} → {_num(lv['2022'], 4)} → {_num(lv['2023'], 4)} → {_num(lv['2024'], 4)} → "
        f"{_num(lv['2025'], 4)} → {_num(lv['ref'], 4)} em {_br_date(data['reference_date'])}); positivo = real "
        "desvalorizou. Carteira em BRL = (1 + retorno USD) × (1 + variação USD/BRL) − 1.")

    # ── Valuation ──
    _section("💰 Valuation e fundamentos (carteira de cada ETF)")
    vrows = []
    for e in etfs:
        vrows.append({"cells": [
            _pill(e["key"]), _mult(e["pe"]), _mult(e["fpe"]), _mult(e["pb"], 2), _pct(e["roe"], 1),
            _pct(e["dy"]), _mult(e["ps"], 2), _mult(e["pcf"]), _pct(e["net_margin"], 1),
            _pct(e["debt_cap"], 1), _pct(e["eg_lt"], 1), _num(e["n_stocks"], 0),
        ]})
    vrows.append({"_style": f"background:{TAG_VINHO}0d;font-weight:700", "cells": [
        "<b>Carteira TAG</b>", _mult(port["pe"]), _mult(port["fpe"]), _mult(port["pb"], 2),
        _pct(port["roe"], 1), _pct(port["dy"]), _mult(port["ps"], 2), _mult(port["pcf"]),
        _pct(port["net_margin"], 1), _pct(port["debt_cap"], 1), _pct(port["eg_lt"], 1), "—"]})
    xp, xb = xray["price_ratios"], xray["profitability"]
    vrows.append({"_style": "background:#f7f7f7", "cells": [
        "X-Ray Carteira TAG", _mult(xp["portfolio"]["pe"]), "—", _mult(xp["portfolio"]["pb"], 2),
        _pct(xb["portfolio"]["roe"], 1), "—", _mult(xp["portfolio"]["ps"], 2), _mult(xp["portfolio"]["pcf"]),
        _pct(xb["portfolio"]["net_margin"], 1), _pct(xb["portfolio"]["debt_capital"], 1), "—", "—"]})
    vrows.append({"_style": "background:#f7f7f7", "cells": [
        "X-Ray S&P 500 (bench)", _mult(xp["benchmark"]["pe"]), "—", _mult(xp["benchmark"]["pb"], 2),
        _pct(xb["benchmark"]["roe"], 1), "—", _mult(xp["benchmark"]["ps"], 2), _mult(xp["benchmark"]["pcf"]),
        _pct(xb["benchmark"]["net_margin"], 1), _pct(xb["benchmark"]["debt_capital"], 1), "—", "—"]})
    _table(["ETF", "P/E TTM", "P/E Fwd", "P/BV", "ROE", "Div. Yield", "P/S", "P/CF", "Margem líq.",
            "Dív./Capital", "Cresc. LP lucro", "Nº ações"], vrows, min_width=1100)
    st.caption(
        "Múltiplos Morningstar da carteira de cada ETF (média ponderada pelos ativos; P/E negativo excluído e "
        "P/E > 60x limitado a 60x). P/E Fwd = preço ÷ lucro projetado do ano corrente. BKCH sem P/E TTM "
        "(lucro agregado negativo). Carteira TAG = média harmônica ponderada para múltiplos e média aritmética "
        f"para ROE/yield/margem. X-Ray Morningstar com portfólio de {_br_date(xray['as_of'])}.")

    # Gráfico P/E TTM vs Fwd
    fig = go.Figure()
    keys = [e["key"] for e in etfs] + ["Carteira"]
    fig.add_bar(name="P/E TTM", x=keys, y=[e["pe"] for e in etfs] + [port["pe"]], marker_color=TAG_VINHO,
                text=[_num(v, 1) if v else "" for v in [e["pe"] for e in etfs] + [port["pe"]]], textposition="outside")
    fig.add_bar(name="P/E Fwd", x=keys, y=[e["fpe"] for e in etfs] + [port["fpe"]], marker_color=TAG_LARANJA,
                text=[_num(v, 1) if v else "" for v in [e["fpe"] for e in etfs] + [port["fpe"]]], textposition="outside")
    fig.update_layout(height=300, barmode="group", margin=dict(l=0, r=0, t=20, b=0),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fff",
                      font=dict(family="Arial, sans-serif", size=11, color="#555"),
                      legend=dict(orientation="h", y=1.12, x=0),
                      yaxis=dict(ticksuffix="x", gridcolor="#eee", griddash="dot",
                                 range=[0, max(v for v in [e["pe"] for e in etfs] + [port["pe"]] if v) * 1.18]))
    st.plotly_chart(fig, use_container_width=True)



# ===================== ESTRATÉGIA & ECOSSISTEMA =====================
def render_strategy():
    data = _load()
    etfs, port, xray = data["etfs"], data["portfolio"], data["xray"]
    _section("🧭 Estratégia e ecossistema de cada ETF")
    cols = st.columns(2)
    for i, e in enumerate(etfs):
        with cols[i % 2]:
            with st.expander(f"{e['key']} · {e['name']} — {_pct(e['weight'], 1)}", expanded=True):
                st.markdown(
                    f"<div style='font-size:12.5px;color:#333'>"
                    f"<b>Camada:</b> {e['camada']}<br><b>Listagem:</b> {e['listing']}<br>"
                    f"<b>Índice:</b> {e['index']}<br><b>Categoria Morningstar:</b> {e['category']} · "
                    f"<b>Início:</b> {_br_date(e['inception'])} · <b>Taxa:</b> {_pct(e['ter'])}"
                    f"<p style='margin:8px 0'>{e['estrategia']}</p><b>Ecossistema:</b><ul style='margin:4px 0'>"
                    + "".join(f"<li>{x}</li>" for x in e["ecossistema"]) + "</ul></div>",
                    unsafe_allow_html=True)



# ===================== TOP 10 POR ETF =====================
def render_top10():
    data = _load()
    etfs, port, xray = data["etfs"], data["portfolio"], data["xray"]
    _section("🔟 Top 10 posições de cada ETF — valuation por ação")
    labels = [f"{e['key']} — {e['name']}" for e in etfs]
    sel = st.radio("ETF", labels, index=0, key="tag_eq_etf_top10", horizontal=True,
                   format_func=lambda l: l.split(" — ")[0])
    key = etfs[labels.index(sel)]["key"]
    st.markdown(f"<p style='color:{TAG_GRAY};font-size:0.85rem;margin:0'>{sel}</p>", unsafe_allow_html=True)
    _stock_table(data["top10"][key], weight_label=f"% {key}")
    if key == "DRAM":
        st.caption("DRAM: posição direta + swaps somados por empresa (exposição econômica). "
                   "~37% do patrimônio em T-Bills/money market como colateral dos swaps não aparece no top 10.")
    top_w = sum(r["weight"] for r in data["top10"][key])
    st.caption(f"Top 10 = {_pct(top_w, 1)} do {key}.")



# ===================== CARTEIRA TAG (LOOK-THROUGH) =====================
def render_lookthrough():
    data = _load()
    etfs, port, xray = data["etfs"], data["portfolio"], data["xray"]
    lt = data["lookthrough"]
    agg10 = data["lookthrough_top10"]
    _section("🏆 Top posições da carteira de bolsa TAG (look-through pelos pesos dos ETFs)")
    n_show = st.radio("Mostrar", [10, 25], horizontal=True, key="tag_eq_lt_n", format_func=lambda n: f"Top {n}")
    _stock_table(lt[:n_show], weight_label="% Carteira TAG", show_sources=True)
    st.markdown(
        f"<div style='font-size:12.5px;color:#333;margin-top:6px'><b>Top 10 agregado</b> "
        f"({_pct(agg10['weight'], 1)} da carteira): P/E TTM {_mult(agg10['pe'])} · P/E Fwd {_mult(agg10['fpe'])} · "
        f"P/BV {_mult(agg10['pb'], 2)} · ROE {_pct(agg10['roe'], 1)} · Div. Yield {_pct(agg10['dy'])} · "
        f"Preço/Fair Value médio {_num(agg10['pfv'], 2)}</div>", unsafe_allow_html=True)
    st.caption(
        "Look-through = Σ (peso do ETF × peso da ação no ETF), usando as 25 maiores posições de cada ETF. "
        "Alphabet A+C consolidadas; DRAM com swaps atribuídos à ação subjacente. Market cap convertido para USD "
        "pelo câmbio de 29/09/2026. P/E TTM > 200x ou negativo exibido como n.s. Preço/Fair Value < 1 = abaixo do "
        "valor justo estimado pela Morningstar.")

    # Barras empilhadas: origem da exposição
    top = lt[:15]
    fig = go.Figure()
    for k in [e["key"] for e in etfs]:
        fig.add_bar(name=k, y=[r["name"] for r in top], x=[r["sources"].get(k, 0) for r in top],
                    orientation="h", marker_color=ETF_COLORS[k],
                    hovertemplate=f"{k}: %{{x:.2f}}%<extra></extra>")
    fig.update_layout(height=460, barmode="stack", margin=dict(l=0, r=0, t=30, b=0),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fff",
                      font=dict(family="Arial, sans-serif", size=11, color="#555"),
                      legend=dict(orientation="h", y=1.08, x=0),
                      xaxis=dict(ticksuffix="%", gridcolor="#eee", griddash="dot"),
                      yaxis=dict(autorange="reversed"),
                      title=dict(text="De onde vem a exposição (top 15)", font=dict(size=13, color=TAG_VINHO)))
    st.plotly_chart(fig, use_container_width=True)

    # ── Setores X-Ray ──
    _section("🏭 Setores — Carteira TAG vs. S&P 500 (X-Ray Morningstar)")
    sec = xray["sectors"]
    names = list(sec.keys())
    fig = go.Figure()
    fig.add_bar(name="Carteira TAG", x=names, y=[sec[n][0] for n in names], marker_color=TAG_VINHO,
                text=[_num(sec[n][0], 1) for n in names], textposition="outside")
    fig.add_bar(name="S&P 500", x=names, y=[sec[n][1] for n in names], marker_color="#c9c6bd",
                text=[_num(sec[n][1], 1) for n in names], textposition="outside")
    fig.update_layout(height=320, barmode="group", margin=dict(l=0, r=0, t=20, b=0),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fff",
                      font=dict(family="Arial, sans-serif", size=11, color="#555"),
                      legend=dict(orientation="h", y=1.12, x=0),
                      yaxis=dict(ticksuffix="%", gridcolor="#eee", griddash="dot",
                                 range=[0, max(max(v) for v in sec.values()) * 1.18]))
    st.plotly_chart(fig, use_container_width=True)

    st.caption(f"Fonte: {data['source']}.")


def _stock_table(rows, weight_label, show_sources=False):
    headers = ["Empresa", "Ticker", "País", "Setor", weight_label]
    if show_sources:
        headers.append("Via")
    headers += ["Mkt cap", "Preço", "Dia", "YTD", "12M", "P/E TTM", "P/E Fwd", "P/BV", "ROE",
                "Div. Yield", "P/FV", "Moat"]
    out = []
    for r in rows:
        pe = "n.s." if r.get("pe_ns") else _mult(r.get("pe"))
        cells = [r["name"], r.get("ticker", "—"), r.get("country", "—"), r.get("sector", "—"),
                 f"<b>{_pct(r['weight'])}</b>"]
        if show_sources:
            cells.append(" ".join(_pill(k) for k in r["sources"]))
        cells += [
            _bn(r.get("mcap_usd_bn")),
            "—" if r.get("price") is None else f"{r['cur']} {_num(r['price'])}",
            _ret(r.get("r1d")), _ret(r.get("ytd")), _ret(r.get("r1y")),
            pe, _mult(r.get("fpe")), _mult(r.get("pb"), 2), _pct(r.get("roe"), 1), _pct(r.get("dy")),
            _pfv(r.get("pfv")), _moat(r.get("moat")),
        ]
        out.append({"cells": cells})
    _table(headers, out, min_width=1350)
