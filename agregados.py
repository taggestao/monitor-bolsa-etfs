"""
agregados.py — agregação da carteira TAG a partir dos dados de cada ETF e das holdings.

Usado por build_tag_equities.py (pesos oficiais, ao gerar o JSON) e pelo app (views.py), que
recalcula tudo em tempo real quando o usuário digita outros pesos para os ETFs.
"""
from carteira import ISSUER_ALIAS, ISSUER_NAME, dram_consolidated

RET_FIELDS = ("r1d", "mtd", "r3m", "ytd", "r1y", "r2y", "r3y")
HARMONIC_FIELDS = ("pe", "fpe", "pb", "fpb", "ps", "pcf")
ARITH_FIELDS = ("roe", "dy", "net_margin", "debt_cap", "eg_lt", "ter")


def harmonic(pairs):
    """Média harmônica ponderada (padrão para múltiplos de carteira): 1 / Σ w·(1/x)."""
    pairs = [(w, x) for w, x in pairs if w and x not in (None, 0) and x > 0]
    tw = sum(w for w, _ in pairs)
    return (tw / sum(w / x for w, x in pairs), tw) if pairs else (None, 0)


def arith(pairs):
    pairs = [(w, x) for w, x in pairs if w and x is not None]
    tw = sum(w for w, _ in pairs)
    return (sum(w * x for w, x in pairs) / tw, tw) if pairs else (None, 0)


def portfolio(etfs, weights):
    """Retornos (média ponderada) e fundamentos (múltiplos: média harmônica) da carteira.
    `_cov` = % da carteira com o dado; a média é renormalizada para esses ETFs."""
    w = {e["key"]: weights[e["key"]] / 100 for e in etfs}
    out = {}
    for fields, fn in ((RET_FIELDS, arith), (HARMONIC_FIELDS, harmonic), (ARITH_FIELDS, arith)):
        for f in fields:
            v, cov = fn([(w[e["key"]], e.get(f)) for e in etfs])
            out[f], out[f + "_cov"] = v, cov * 100
    return out


def entry_summary(etfs, weights):
    """Média dos temas desde a entrada, ponderada pelo peso de cada tema, vs. o CSPX nas mesmas
    janelas. excess_total = Σ peso × (tema − CSPX), em p.p. da carteira inteira."""
    th = [e for e in etfs if e.get("since_entry") is not None and weights[e["key"]] > 0]
    tw = sum(weights[e["key"]] for e in th)
    if not th or not tw:
        return None
    avg = sum(weights[e["key"]] * e["since_entry"] for e in th) / tw
    avg_c = sum(weights[e["key"]] * e["cspx_since_entry"] for e in th) / tw
    return {"weight": tw, "avg": avg, "avg_cspx": avg_c, "diff": avg - avg_c, "n": len(th),
            "excess_total": sum(weights[e["key"]] / 100 * (e["since_entry"] - e["cspx_since_entry"]) for e in th)}


def calendar_portfolio(rows, years, weights):
    """Retorno da carteira por ano: média pelos pesos, renormalizada para os ETFs com ano completo."""
    port, cov = {}, {}
    for y in years:
        k = str(y)
        v, c = arith([(weights[r["key"]], r["returns"].get(k, r["returns"].get(y))) for r in rows
                      if not (r["flags"].get(k) or r["flags"].get(y))])
        port[k], cov[k] = v, c
    return port, cov


def top10(holdings, stock_rows):
    """Top 10 de cada ETF; DRAM com posição direta + swaps (+ ADR/preferencial) somados por empresa."""
    out = {}
    for key, rows in holdings.items():
        rows = [r for r in rows if r[2] != "CASH"]
        if key == "DRAM":
            rows = dram_consolidated(rows)
        out[key] = [{"name": n, "weight": w, "ms_id": m, **(stock_rows.get(m) or {})} for n, w, m in rows[:10]]
    return out


def lookthrough(holdings, weights, stock_rows, n=25):
    """Exposição da carteira a cada empresa = Σ (peso do ETF × peso da ação no ETF)."""
    agg = {}
    for key, rows in holdings.items():
        wf = weights.get(key, 0) / 100
        if not wf:
            continue
        for name, wgt, ms_id in rows:
            if ms_id == "CASH":
                continue
            issuer = ISSUER_ALIAS.get(ms_id, ms_id) if ms_id else name
            a = agg.setdefault(issuer, {"ms_id": issuer if ms_id else None, "name": ISSUER_NAME.get(issuer, name),
                                        "weight": 0.0, "sources": {}})
            a["weight"] += wf * wgt
            a["sources"][key] = a["sources"].get(key, 0.0) + wf * wgt
    rows = sorted(agg.values(), key=lambda r: -r["weight"])[:n]
    for r in rows:
        r.update(stock_rows.get(r["ms_id"]) or {})
        r["sources"] = dict(sorted(r["sources"].items(), key=lambda kv: -kv[1]))
    t10 = rows[:10]
    agg10 = {
        "weight": sum(r["weight"] for r in t10),
        "pe": harmonic([(r["weight"], r.get("pe")) for r in t10])[0],
        "fpe": harmonic([(r["weight"], r.get("fpe")) for r in t10])[0],
        "pb": harmonic([(r["weight"], r.get("pb")) for r in t10])[0],
        "roe": arith([(r["weight"], r.get("roe")) for r in t10])[0],
        "dy": arith([(r["weight"], r.get("dy")) for r in t10])[0],
        "pfv": arith([(r["weight"], r.get("pfv")) for r in t10])[0],
    }
    return rows, agg10
