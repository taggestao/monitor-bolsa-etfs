# views.py — Monitor de Bolsa TAG (ETFs): seções do app (visão geral, estratégia, top 10, look-through).
# Dados: tag_equities.json, gerado por build_tag_equities.py (Morningstar MCP).
# =============================================================================
import copy
import json
import os
import urllib.request
from datetime import date, timedelta

import plotly.graph_objects as go
import streamlit as st

import agregados as AG

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
def _load_file(mtime):
    # mtime entra na chave do cache: quando o JSON é atualizado (deploy da rotina diária),
    # a próxima abertura do app já lê os dados novos.
    with open(_DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


# Seletor de data final: um fechamento mensal (AAAA-MM-DD) ou "diario" (último pregão). Aparece na barra
# lateral (PERIOD_KEY) e na aba Carteira TAG (PERIOD_KEY_LT); os dois ficam sincronizados.
PERIOD_KEY = "periodo"
PERIOD_KEY_LT = "periodo_lt"
DAILY = "diario"
WEIGHT_KEY = "peso_{}"   # pesos digitados pelo usuário (aba Carteira TAG), um por ETF
_RET_FIELDS = ("mtd", "r3m", "ytd", "r1y", "r2y", "r3y", "vol1y", "vol_note", "since_inception",
               "since_entry", "cspx_since_entry")


def _base():
    return _load_file(os.path.getmtime(_DATA_FILE))


def period_options():
    """[(valor, rótulo)] do seletor: fechamentos mensais (mais recente primeiro) + último pregão."""
    base = _base()
    months = sorted(base.get("periods", {}), reverse=True)
    opts = [(m, f"{_br_date(m)} · fechamento mensal") for m in months]
    opts.append((DAILY, f"{_br_date(base['reference_date'])} · último pregão"))
    return opts, base.get("default_period", DAILY)


def init_state():
    """Valores iniciais do seletor de data e dos pesos (antes de qualquer widget ou cálculo)."""
    base = _base()
    opts, default = period_options()
    valid = {v for v, _ in opts}
    if st.session_state.get(PERIOD_KEY) not in valid:
        st.session_state[PERIOD_KEY] = default if default in valid else opts[0][0]
    st.session_state[PERIOD_KEY_LT] = st.session_state[PERIOD_KEY]
    for k, w in base["official_weights"].items():
        st.session_state.setdefault(WEIGHT_KEY.format(k), float(w))


def sync_period(src):
    """on_change dos seletores de data: copia o valor escolhido para o outro seletor."""
    other = PERIOD_KEY_LT if src == PERIOD_KEY else PERIOD_KEY
    st.session_state[other] = st.session_state[src]


def reset_weights():
    for k, w in _base()["official_weights"].items():
        st.session_state[WEIGHT_KEY.format(k)] = float(w)


def weights():
    """(pesos normalizados para 100%, soma digitada, personalizado?)"""
    off = _base()["official_weights"]
    raw = {k: float(st.session_state.get(WEIGHT_KEY.format(k), w) or 0) for k, w in off.items()}
    tot = sum(raw.values())
    if tot <= 0:
        return dict(off), tot, False
    return {k: v * 100 / tot for k, v in raw.items()}, tot, any(abs(raw[k] - off[k]) > 1e-9 for k in off)


@st.cache_data(show_spinner=False)
def _view(mtime, period, wkey, custom):
    """Dados do app na data final `period` (fechamento mensal ou DAILY) e com os pesos `wkey`."""
    data = copy.deepcopy(_load_file(mtime))
    data["snapshot_date"] = data["reference_date"]
    month = period != DAILY and period in data.get("periods", {})
    if month:
        p = data["periods"][period]
        for e in data["etfs"]:
            e.update({f: p["etfs"][e["key"]].get(f) for f in _RET_FIELDS})
            e["r1d"] = None
        data["calendar"] = p["calendar"]
        m = date.fromisoformat(period)
        data["reference_date"] = period
        data["mo_end_date"] = (m.replace(day=1) - timedelta(days=1)).isoformat()
    for e in data["etfs"]:
        e.setdefault("r3m", None)
    data["mode"] = "month" if month else "daily"

    # ── Pesos: carteira, desde a entrada e ano-calendário recalculados ──
    w = dict(wkey)
    for e in data["etfs"]:
        e["weight"] = w[e["key"]]
    data["portfolio"].update(AG.portfolio(data["etfs"], w))
    data["entry_summary"] = AG.entry_summary(data["etfs"], w)
    cal = data["calendar"]
    cal["portfolio"], cal["portfolio_cov"] = AG.calendar_portfolio(cal["rows"], cal["years"], w)
    for r in cal["rows"]:
        r["weight"] = w[r["key"]]
    data["custom_weights"] = custom

    # ── Holdings e ações na data final ──
    hist = data["holdings_history"]
    target = date.fromisoformat(data["reference_date"])
    hdate = min(hist, key=lambda d: (abs((date.fromisoformat(d) - target).days), d))
    holdings = {k: [tuple(r) for r in v] for k, v in hist[hdate].items()}
    rows = copy.deepcopy(data["stock_rows"])
    if month:
        sp = data.get("stock_periods", {}).get(period, {})
        for k, r in rows.items():
            r.update({"r1d": None, "mtd": None, "ytd": None, "r1y": None, **sp.get(k, {})})
    data["top10"] = AG.top10(holdings, rows)
    data["lookthrough"], data["lookthrough_top10"] = AG.lookthrough(holdings, w, rows)
    data["holdings_used_date"] = hdate
    return data


def _load():
    w, _, custom = weights()
    sel = st.session_state.get(PERIOD_KEY) or _base().get("default_period", DAILY)
    return _view(os.path.getmtime(_DATA_FILE), sel, tuple(sorted(w.items())), custom)


def load_data():
    return _load()


# ── PTAX (Banco Central) na data escolhida — busca em tempo de execução, com fallback ──
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _fetch_ptax(day):
    d = date.fromisoformat(day)
    ini, fim = (d - timedelta(days=10)).strftime("%m-%d-%Y"), d.strftime("%m-%d-%Y")
    url = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
           "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
           f"?@dataInicial=%27{ini}%27&@dataFinalCotacao=%27{fim}%27&$format=json")
    with urllib.request.urlopen(url, timeout=8) as r:
        vals = json.load(r)["value"]
    last = max(vals, key=lambda v: v["dataHoraCotacao"])
    return float(last["cotacaoVenda"]), last["dataHoraCotacao"][:10]


def _ptax(day, fallback=None):
    """(cotação, data) da PTAX venda no último dia útil até `day`; fallback se o BCB não responder."""
    try:
        return _fetch_ptax(day)
    except Exception:
        return fallback


def _calendar_brl(data):
    """Variação USD/BRL (PTAX) e carteira em BRL para os anos do calendário."""
    cal = data["calendar"]
    ye = {int(k): v for k, v in data["usdbrl_year_end"].items()}
    ref = data["reference_date"]
    ref_y = int(ref[:4])
    fallback = None
    if data.get("usdbrl_ref_date") and data["usdbrl_ref_date"] <= ref:
        fallback = (data["usdbrl_ref"], data["usdbrl_ref_date"])
    if ref[5:] == "12-31" and ref_y in ye:
        end = (ye[ref_y], ref)
    else:
        end = _ptax(ref, fallback)
    fx, brl = {}, {}
    for y in cal["years"]:
        a = ye.get(int(y) - 1)
        b = end[0] if int(y) == ref_y and end else ye.get(int(y)) if int(y) != ref_y else None
        fx[y] = None if a is None or b is None else (b / a - 1) * 100
        pu = cal["portfolio"].get(y) if y in cal["portfolio"] else cal["portfolio"].get(str(y))
        brl[y] = None if fx[y] is None or pu is None else ((1 + pu / 100) * (1 + fx[y] / 100) - 1) * 100
    return fx, brl, end, ye


def render_header_note():
    data = _load()
    ref = _br_date(data["reference_date"])
    mo_end = _br_date(data["mo_end_date"])
    snap = _br_date(data["snapshot_date"])
    if data["mode"] == "month":
        when = (f"📅 Retornos no <b>fechamento mensal de {ref}</b> (retorno mensal Morningstar); preço, AUM, "
                f"valuation e ações do último pregão (<b>{snap}</b>); holdings de "
                f"<b>{_br_date(data['holdings_date'])}</b>. Troque a data final na barra lateral.")
    else:
        when = (f"📅 Preços e retornos diários até <b>{ref}</b>; retornos 24M/36M e vol 12M com fechamento "
                f"mensal de <b>{mo_end}</b>; holdings de <b>{_br_date(data['holdings_date'])}</b>.")
    st.markdown(
        "<p style='font-size:0.85rem;color:#666;margin-bottom:0.8rem'>"
        "Carteira de bolsa TAG — 7 ETFs com foco no ecossistema de IA (compute, memória, energia, "
        "segurança, infraestrutura e cripto/HPC) sobre um núcleo de S&P 500. Dados Morningstar (MCP). "
        f"{when}</p>",
        unsafe_allow_html=True,
    )


# ===================== VISÃO GERAL =====================
def render_overview():
    data = _load()
    etfs, port, xray = data["etfs"], data["portfolio"], data["xray"]
    mo_end = _br_date(data["mo_end_date"])

    # ── KPIs da carteira ──
    monthly = data["mode"] == "month"
    kpis = "".join([
        _kpi("3 meses", _pct(port["r3m"]), "média ponderada") if monthly
        else _kpi("Retorno dia", _pct(port["r1d"]), "média ponderada"),
        _kpi("Mês" if monthly else "MTD", _pct(port["mtd"]), f"desde {mo_end}"),
        _kpi("YTD", _pct(port["ytd"]), f"{_num(port['ytd_cov'], 0)}% da carteira c/ dado"),
        _kpi("12 meses", _pct(port["r1y"]), f"{_num(port['r1y_cov'], 0)}% da carteira c/ dado"),
        _kpi("P/E TTM", _mult(port["pe"]), f"X-Ray: {_mult(xray['price_ratios']['portfolio']['pe'])}"),
        _kpi("P/E Fwd", _mult(port["fpe"]), "lucro projetado"),
        _kpi("P/BV", _mult(port["pb"], 2), f"X-Ray: {_mult(xray['price_ratios']['portfolio']['pb'], 2)}"),
        _kpi("ROE", _pct(port["roe"], 1), f"X-Ray: {_pct(xray['profitability']['portfolio']['roe'], 1)}"),
        _kpi("Div. Yield", _pct(port["dy"]), "trailing 12m"),
    ])
    st.markdown(f"<div style='display:flex;gap:6px;overflow-x:auto'>{kpis}</div>", unsafe_allow_html=True)

    # ── Destaque: retorno desde a entrada de cada tema ──
    themes = sorted([e for e in etfs if e.get("entry_date") and e.get("since_entry") is not None],
                    key=lambda e: e["entry_date"])
    cards = ""
    for e in themes:
        r, diff = e["since_entry"], e["since_entry"] - e["cspx_since_entry"]
        rc = TAG_GREEN if r >= 0 else TAG_RED
        cards += (
            f"<div style='background:#fff;border:1px solid rgba(99,13,36,0.15);"
            f"border-top:4px solid {ETF_COLORS[e['key']]};border-radius:10px;padding:8px 10px;flex:1 1 0;min-width:0'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center'>{_pill(e['key'])}"
            f"<span style='font-size:10.5px;color:{TAG_GRAY};white-space:nowrap'>{_br_date(e['entry_date'])}</span></div>"
            f"<div style='font-size:1.3rem;font-weight:700;color:{rc};margin-top:4px'>"
            f"{'+' if r >= 0 else ''}{_pct(r)}</div>"
            f"<div style='font-size:11px;color:{TAG_GRAY}'>vs. CSPX: {_pp(diff)}</div></div>")
    es = data["entry_summary"]
    if es is None:
        st.info("Nenhum tema da carteira tinha entrado até a data final escolhida (ou todos estão com peso zero).")
    beat = es is not None and es["diff"] >= 0
    bc = TAG_GREEN if beat else TAG_RED
    cards += "" if es is None else (
        f"<div style='background:{TAG_VINHO};color:#fff;border-radius:10px;padding:8px 12px;flex:1.35 1 0;min-width:0'>"
        f"<div style='font-size:11px;font-weight:700;letter-spacing:.3px;opacity:.9'>MÉDIA PONDERADA DOS TEMAS</div>"
        f"<div style='display:flex;gap:10px;align-items:baseline;margin-top:4px'>"
        f"<span style='font-size:1.3rem;font-weight:700'>{'+' if es['avg'] >= 0 else ''}{_pct(es['avg'])}</span>"
        f"<span style='font-size:11px;opacity:.85'>vs. S&P {'+' if es['avg_cspx'] >= 0 else ''}{_pct(es['avg_cspx'])}</span></div>"
        f"<div style='font-size:11px;margin-top:2px'><span style='background:#fff;color:{bc};font-weight:700;"
        f"padding:0 6px;border-radius:6px'>{'▲ bate' if beat else '▼ perde para'} o S&P "
        f"{'+' if es['diff'] >= 0 else ''}{_num(es['diff'], 2)} p.p.</span></div></div>")
    if es is not None:
        st.markdown(
            f"<div style='margin:14px 0 4px 0;font-size:12px;font-weight:700;color:{TAG_VINHO};"
            f"text-transform:uppercase;letter-spacing:.4px'>🎯 Retorno desde a entrada de cada tema (USD)</div>"
            f"<div style='display:flex;gap:6px;overflow-x:auto'>{cards}</div>"
            f"<div style='font-size:11.5px;color:{TAG_GRAY};margin-top:4px'>Média ponderada pelo peso de cada tema na "
            f"carteira TAG ({_pct(es['weight'], 0)} do total, {es['n']} temas) vs. o S&P 500 (CSPX) nas mesmas janelas. "
            f"Efeito na carteira inteira vs. manter esse capital no S&P: <b style='color:{bc}'>"
            f"{'+' if es['excess_total'] >= 0 else ''}{_num(es['excess_total'], 2)} p.p.</b></div>",
            unsafe_allow_html=True)

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
            _bn(e["avg_mcap_usd_bn"]), _ret(e["r3m"] if monthly else e["r1d"]), _ret(e["mtd"]), _ret(e["ytd"]), r1y,
            _ret(e["r2y"]), _ret(e["r3y"]), vol,
        ]})
    rows.append({"_style": f"background:{TAG_VINHO}0d;font-weight:700", "cells": [
        "<b>Carteira TAG</b>", "100%", "—", "—", "—", _ret(port["r3m"] if monthly else port["r1d"]), _ret(port["mtd"]),
        _ret(port["ytd"]), _ret(port["r1y"]), _ret(port["r2y"]), _ret(port["r3y"]), "—"]})
    _table(["ETF", "Peso", f"Preço ({_br_date(data['snapshot_date'])})" if monthly else "Preço", "AUM",
            "Mkt cap médio", "3M" if monthly else "Dia", "Mês" if monthly else "MTD", "YTD", "12M",
            "24M a.a.", "36M a.a.", "Vol 12M"], rows, min_width=1100)
    st.caption(
        (f"Retornos totais em USD até o fechamento de {_br_date(data['reference_date'])}, encadeando os retornos "
         "mensais do Morningstar; vol 12M = desvio-padrão dos 12 retornos mensais × √12. Preço, AUM e mkt cap do "
         f"último pregão ({_br_date(data['snapshot_date'])}). " if monthly else "") +
        "Mkt cap médio = média geométrica do valor de mercado das ações do ETF (Morningstar). "
        "24M/36M anualizados. Carteira = média dos ETFs pelos pesos atuais, renormalizada para os ETFs com "
        "dado no período (DRAM só existe desde 01/04/2026; BRIJ desde 03/09/2024). "
        "† DRAM: retorno desde o início (01/04/2026). * DRAM: vol anualizada desde o início.")

    # ── Retorno desde a entrada de cada tema na carteira ──
    _section("🎯 Retorno desde a entrada de cada tema na carteira TAG")
    ref_d = date.fromisoformat(data["reference_date"])
    erows = []
    for e in sorted([e for e in etfs if e.get("entry_date") and e.get("since_entry") is not None],
                    key=lambda e: e["entry_date"]):
        days = (ref_d - date.fromisoformat(e["entry_date"])).days
        erows.append({"cells": [
            _pill(e["key"]), e["camada"], _pct(e["weight"], 1), _br_date(e["entry_date"]), _num(days, 0),
            _ret(e["since_entry"]), _ret(e["cspx_since_entry"]), _pp(e["since_entry"] - e["cspx_since_entry"]),
        ]})
    es = data["entry_summary"]
    if es is not None:
        erows.append({"_style": f"background:{TAG_VINHO}0d;font-weight:700", "cells": [
            "<b>Média ponderada</b>", f"{es['n']} temas", _pct(es["weight"], 1), "—", "—",
            _ret(es["avg"]), _ret(es["avg_cspx"]), _pp(es["diff"], 2)]})
        erows.append({"_style": "background:#f7f7f7", "cells": [
            "Efeito na carteira TAG", "Σ peso × (tema − CSPX)", "100%", "—", "—", "—", "—",
            _pp(es["excess_total"], 2)]})
    _table(["Tema", "Camada", "Peso", "Entrada", "Dias", "Retorno desde a entrada", "CSPX no período",
            "Diferença vs. CSPX"], erows, min_width=900)
    st.caption(
        "Retorno total em USD do fechamento da data de entrada até "
        f"{_br_date(data['reference_date'])} (Daily Return Index Morningstar). CSPX no período = S&P 500 (núcleo "
        "da carteira) entre as mesmas datas; diferença em pontos percentuais. Períodos curtos, sem anualizar. "
        "Média ponderada = Σ peso × retorno ÷ Σ pesos dos temas (cada tema na sua própria janela); o S&P é ponderado "
        "da mesma forma, então a comparação é justa. Efeito na carteira = quanto os temas somaram (ou tiraram) do "
        "retorno total da carteira TAG vs. ter o mesmo capital no S&P 500.")

    # ── Retorno por ano-calendário + USD/BRL ──
    _section("📅 Retorno por ano-calendário (USD) e variação cambial")
    cal = data["calendar"]
    years = [str(y) for y in cal["years"]]
    full_year = data["reference_date"][5:] == "12-31"
    head = [f"{y} (YTD)" if y == years[0] and not full_year else y for y in years]
    fx, brl, fx_end, ye = _calendar_brl(data)
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
                  + [_ret(fx.get(y, fx.get(int(y)))) for y in years]})
    crows.append({"_style": "background:#f7f7f7;font-weight:700", "cells":
                  ["<b>Carteira TAG em BRL</b>", "—"] + [_ret(brl.get(y, brl.get(int(y)))) for y in years]})
    _table(["ETF", "Peso"] + head, crows, min_width=760)
    cov_txt = " · ".join(f"{y}: {_num(cal['portfolio_cov'][y], 0)}%" for y in years)
    st.caption(
        f"Retorno total em USD. {years[0]} = acumulado no ano até {_br_date(data['reference_date'])}. "
        "Em branco: ETF ainda não existia ou teve ano parcial de lançamento (BRIJ 03/09/2024, GRDU 14/04/2022). "
        "† DRAM: desde o início (01/04/2026), fora da média da carteira. Carteira = média pelos pesos atuais, "
        f"renormalizada para os ETFs com ano completo (cobertura — {cov_txt}). "
        "USD/BRL = variação da PTAX venda do Banco Central entre fins de ano (R$ "
        + " → ".join(_num(ye.get(int(y) - 1), 4) for y in reversed(years))
        + (f" → {_num(fx_end[0], 4)} em {_br_date(fx_end[1])}" if fx_end
           else " → PTAX da data final indisponível no momento (Banco Central não respondeu)")
        + "); positivo = real desvalorizou. Carteira em BRL = (1 + retorno USD) × (1 + variação USD/BRL) − 1.")

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
    _stock_table(data["top10"][key], weight_label=f"% {key}", monthly=data["mode"] == "month")
    if key == "DRAM":
        cash = sum(r[1] for r in data["holdings_history"][data["holdings_used_date"]]["DRAM"] if r[2] == "CASH")
        st.caption("DRAM: posição direta + swaps somados por empresa (exposição econômica). "
                   f"{_pct(cash, 0)} do patrimônio em T-Bills/money market/caixa, colateral dos swaps, "
                   "não aparece no top 10.")
    top_w = sum(r["weight"] for r in data["top10"][key])
    st.caption(f"Top 10 = {_pct(top_w, 1)} do {key}. {_dates_note(data)}")



# ===================== CARTEIRA TAG (LOOK-THROUGH) =====================
def render_weights_editor():
    """Pesos de cada ETF digitados pelo usuário: recalculam a carteira em todas as abas."""
    off = _base()["official_weights"]
    _, tot, custom = weights()
    with st.expander("⚖️ Pesos dos ETFs na carteira — digite outros % para simular", expanded=custom):
        cols = st.columns(len(off))
        for col, k in zip(cols, off):
            col.number_input(f"{k} (%)", min_value=0.0, max_value=100.0, step=0.5, format="%.1f",
                             key=WEIGHT_KEY.format(k), help=f"Peso oficial: {_pct(off[k], 1)}")
        c1, c2 = st.columns([3, 1])
        if abs(tot - 100) > 0.05:
            c1.warning(f"Os pesos somam {_pct(tot, 1)}: nos cálculos eles são reescalados para somar 100%.")
        else:
            c1.caption(f"Soma: {_pct(tot, 1)}. "
                       + ("Pesos personalizados valem para todas as abas nesta sessão." if custom
                          else "Pesos oficiais da carteira TAG."))
        c2.button("Restaurar pesos oficiais", on_click=reset_weights, use_container_width=True,
                  disabled=not custom)


def render_lookthrough():
    opts, _ = period_options()
    labels = dict(opts)
    c1, c2 = st.columns([1, 2])
    c1.selectbox("Data final", [v for v, _ in opts], format_func=labels.get, key=PERIOD_KEY_LT,
                 on_change=sync_period, args=(PERIOD_KEY_LT,),
                 help="Fechamento mensal: retornos das ações e da carteira até o fim do mês escolhido. "
                      "Último pregão: dados diários mais recentes. Também muda a data das outras abas.")
    render_weights_editor()
    data = _load()
    etfs, port, xray = data["etfs"], data["portfolio"], data["xray"]
    lt = data["lookthrough"]
    agg10 = data["lookthrough_top10"]
    monthly = data["mode"] == "month"
    pesos = " · ".join(f"{e['key']} {_pct(e['weight'], 1)}" for e in etfs)
    c2.markdown(
        f"<div style='font-size:12.5px;color:#333;margin-top:30px'>"
        f"<b>{'Fechamento de ' + _br_date(data['reference_date']) if monthly else 'Último pregão: ' + _br_date(data['reference_date'])}"
        f"</b> · pesos {'personalizados' if data['custom_weights'] else 'oficiais'}: {pesos}</div>",
        unsafe_allow_html=True)
    _section("🏆 Top posições da carteira de bolsa TAG (look-through pelos pesos dos ETFs)")
    n_show = st.radio("Mostrar", [10, 25], horizontal=True, key="tag_eq_lt_n", format_func=lambda n: f"Top {n}")
    _stock_table(lt[:n_show], weight_label="% Carteira TAG", show_sources=True, monthly=monthly)
    if monthly:
        pr = [(r["weight"], r.get("mtd")) for r in lt[:n_show]]
        pr_y = [(r["weight"], r.get("ytd")) for r in lt[:n_show]]
        m_avg, m_cov = AG.arith(pr)
        y_avg, y_cov = AG.arith(pr_y)
        st.markdown(
            f"<div style='font-size:12.5px;color:#333;margin-top:6px'><b>Top {n_show} no fechamento de "
            f"{_br_date(data['reference_date'])}</b> (média pelo peso na carteira, entre as ações com dado): "
            f"mês {_ret(m_avg)} · YTD {_ret(y_avg)}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:12.5px;color:#333;margin-top:6px'><b>Top 10 agregado</b> "
        f"({_pct(agg10['weight'], 1)} da carteira): P/E TTM {_mult(agg10['pe'])} · P/E Fwd {_mult(agg10['fpe'])} · "
        f"P/BV {_mult(agg10['pb'], 2)} · ROE {_pct(agg10['roe'], 1)} · Div. Yield {_pct(agg10['dy'])} · "
        f"Preço/Fair Value médio {_num(agg10['pfv'], 2)}</div>", unsafe_allow_html=True)
    st.caption(
        "Look-through = Σ (peso do ETF × peso da ação no ETF), usando as 25 maiores posições de cada ETF. "
        "Alphabet A+C, ADRs e preferenciais consolidadas; DRAM com swaps atribuídos à ação subjacente. "
        f"Market cap convertido para USD pelo câmbio de {_br_date(data['fx_date'])}. P/E TTM > 200x ou negativo "
        "exibido como n.s. Preço/Fair Value < 1 = abaixo do valor justo estimado pela Morningstar. "
        + _dates_note(data))

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
    st.caption(f"X-Ray com os pesos oficiais e portfólio de {_br_date(xray['as_of'])} (o Morningstar calcula o "
               "X-Ray só no fechamento mais recente; não muda com a data final nem com os pesos digitados).")
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


def _stock_table(rows, weight_label, show_sources=False, monthly=False):
    headers = ["Empresa", "Ticker", "País", "Setor", weight_label]
    if show_sources:
        headers.append("Via")
    headers += ["Mkt cap"] + (["Mês", "YTD", "12M"] if monthly else ["Preço", "Dia", "YTD", "12M"])
    headers += ["P/E TTM", "P/E Fwd", "P/BV", "ROE", "Div. Yield", "P/FV", "Moat"]
    out = []
    for r in rows:
        pe = "n.s." if r.get("pe_ns") else _mult(r.get("pe"))
        cells = [r["name"], r.get("ticker", "—"), r.get("country", "—"), r.get("sector", "—"),
                 f"<b>{_pct(r['weight'])}</b>"]
        if show_sources:
            cells.append(" ".join(_pill(k) for k in r["sources"]))
        cells.append(_bn(r.get("mcap_usd_bn")))
        if monthly:
            cells += [_ret(r.get("mtd")), _ret(r.get("ytd")), _ret(r.get("r1y"))]
        else:
            cells += ["—" if r.get("price") is None else f"{r['cur']} {_num(r['price'])}",
                      _ret(r.get("r1d")), _ret(r.get("ytd")), _ret(r.get("r1y"))]
        cells += [pe, _mult(r.get("fpe")), _mult(r.get("pb"), 2), _pct(r.get("roe"), 1), _pct(r.get("dy")),
                  _pfv(r.get("pfv")), _moat(r.get("moat"))]
        out.append({"cells": cells})
    _table(headers, out, min_width=1350)


def _dates_note(data):
    """Nota sobre as datas dos dados das ações (retornos, valuation e composição dos ETFs)."""
    ref, snap, hd = (_br_date(data[k]) for k in ("reference_date", "snapshot_date", "holdings_used_date"))
    oldest = min(data["holdings_history"])
    comp = f"composição dos ETFs (holdings) de {hd}"
    if data["holdings_used_date"] == oldest and data["reference_date"] < oldest:
        comp += " (a mais antiga guardada; antes disso o Morningstar não fornece holdings históricas)"
    if data["mode"] == "month":
        return (f"Retornos das ações (Mês, YTD, 12M) no fechamento de {ref}, pelo retorno mensal Morningstar "
                f"(disponível a partir de jan/2025; 12M a partir de dez/2025). Market cap e valuation do último "
                f"pregão ({snap}); {comp}.")
    return f"Preços, retornos e valuation das ações no último pregão ({snap}); {comp}."
