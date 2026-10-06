"""
build_tag_equities.py — Monitor de ETFs da carteira de bolsa TAG (Ecossistema AI).

Processa os dados Morningstar coletados via MCP (Data Tool, Fund Holdings Tool e X-Ray
Portfolio Analysis) e gera tag_equities.json, consumido pelo app (app.py).
Executar a cada atualização dos dados (ou da alocação em PORTFOLIO).

Fontes:
  • Morningstar MCP — preço, AUM, retornos, vol, valuation dos ETFs e das ações, holdings,
    X-Ray da carteira (setores, P/E, P/B, ROE). Dados em morningstar_data.json, atualizados por
    refresh_morningstar.py (ver ATUALIZACAO.md).
  • USD/BRL — PTAX venda do Banco Central no fim de cada ano e na data mais recente coletada.
  • Câmbio (para converter market cap de ações fora dos EUA em USD) — cotações públicas.
"""
import json, math, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(SCRIPT_DIR, "tag_equities.json")


# ── Alocação da carteira de bolsa TAG (%) ──
PORTFOLIO = [
    # key,    peso,  Morningstar ID
    ("CSPX", 50.0, "0P0000SM09"),
    ("CIBR", 10.0, "F00000VWQP"),
    ("BKCH", 10.0, "F000016SOI"),
    ("BRIJ", 10.0, "0P0001TOAU"),
    ("SOXQ", 6.6, "F000016Y1C"),
    ("DRAM", 6.6, "F00001TGL6"),
    ("GRDU", 6.8, "F00001DPBY"),
]

# ── Descritivo de estratégia + ecossistema (PT-BR) ──
# "camada" = elo da cadeia de valor de IA / tecnologia em que o ETF se posiciona.
ETF_INFO = {
    "CSPX": {
        "name": "iShares Core S&P 500 UCITS ETF (Acc)",
        "listing": "CSPX LN · LSE · USD · UCITS (Irlanda)",
        "index": "S&P 500 (net total return)",
        "camada": "Core / beta de mercado",
        "estrategia": (
            "Réplica física do S&P 500: ~500 maiores empresas dos EUA ponderadas por valor de "
            "mercado. É o núcleo (50%) da carteira e dá a exposição ampla às megacaps que "
            "hoje concentram o capex de IA (hyperscalers, NVIDIA, Broadcom)."
        ),
        "ecossistema": [
            "Hyperscalers / plataformas: Microsoft, Amazon, Alphabet, Meta",
            "Compute & semis: NVIDIA, Broadcom, AMD, Micron, Intel",
            "Hardware & consumo: Apple, Tesla",
            "Diversificação fora de tech: saúde (Eli Lilly), financeiro (JPMorgan, Berkshire), energia",
        ],
    },
    "CIBR": {
        "name": "First Trust NASDAQ Cybersecurity ETF",
        "listing": "CIBR US · Nasdaq · USD",
        "index": "Nasdaq CTA Cybersecurity Index",
        "camada": "Segurança da infraestrutura digital",
        "estrategia": (
            "Replica índice de empresas classificadas como cibersegurança pela CTA (Consumer "
            "Technology Association), com teto de peso por ação. A tese: quanto mais dados, "
            "nuvem e agentes de IA, maior a superfície de ataque e o gasto obrigatório em segurança."
        ),
        "ecossistema": [
            "Endpoint & plataforma XDR: CrowdStrike",
            "Firewall / rede / SASE: Palo Alto, Fortinet, Zscaler, Cisco, Check Point",
            "Identidade & acesso: Okta",
            "Edge / CDN / aplicação: Cloudflare, Akamai, F5",
            "Dados & resiliência: Rubrik, NetApp; observabilidade: Datadog, Dynatrace",
            "Semis e serviços de defesa: Broadcom, Thales, Leidos, Accenture",
        ],
    },
    "BKCH": {
        "name": "Global X Blockchain ETF",
        "listing": "BKCH US · Nasdaq · USD",
        "index": "Solactive Blockchain Index",
        "camada": "Cripto + data centers de HPC/IA",
        "estrategia": (
            "Replica índice de empresas cuja receita vem da tecnologia blockchain: mineradoras, "
            "exchanges, emissores de stablecoin e tesourarias cripto. Boa parte das mineradoras "
            "(IREN, Hut 8, Applied Digital, TeraWulf, Core Scientific) está convertendo energia e "
            "sites em data centers de IA/HPC — daí o elo com o ecossistema AI. Alta vol (≈75% a.a.)."
        ),
        "ecossistema": [
            "Exchanges & brokers: Coinbase, Bullish, eToro, Galaxy Digital",
            "Stablecoin / pagamentos: Circle (USDC)",
            "Tesouraria cripto: BitMine (ETH)",
            "Mineradoras → IA/HPC (energia + data centers): IREN, Hut 8, Riot, MARA, CleanSpark, Applied Digital, TeraWulf, Core Scientific, Cipher",
            "Hardware de mineração: Bitdeer, Canaan",
        ],
    },
    "BRIJ": {
        "name": "Global X European Infrastructure Development UCITS ETF",
        "listing": "BRIJ LN · LSE · UCITS (Irlanda)",
        "index": "Mirae Asset European Infrastructure Development Index",
        "camada": "Infra física, defesa e energia (Europa)",
        "estrategia": (
            "Replica índice de empresas europeias ligadas a gasto em infraestrutura: construção e "
            "concessões, aeroportos, cimento, defesa, geração renovável, redes e torres de telecom. "
            "Diversifica a carteira para Europa, setores de valor e dividendos maiores (≈2,9%)."
        ),
        "ecossistema": [
            "Defesa & eletrônica: Thales, Leonardo",
            "Construção & concessões: Vinci, Ferrovial, Eiffage, Skanska, STRABAG, Acciona",
            "Aeroportos / transporte: Aena, ADP, Getlink, Flughafen Zürich",
            "Materiais: Holcim, Buzzi",
            "Energia & redes: Ørsted, Verbund, Redeia, NKT, Nexans",
            "Telecom & torres: Telefónica, Telecom Italia, Cellnex",
        ],
    },
    "SOXQ": {
        "name": "Invesco PHLX Semiconductor ETF",
        "listing": "SOXQ US · Nasdaq · USD",
        "index": "PHLX Semiconductor Index (SOX)",
        "camada": "Compute: semicondutores",
        "estrategia": (
            "Replica o índice SOX: as 30 maiores empresas de semicondutores listadas nos EUA, "
            "ponderação por valor de mercado modificada (teto por papel). Taxa de 0,19%. É a "
            "cadeia de chips inteira — do design de GPU/ASIC ao equipamento de litografia."
        ),
        "ecossistema": [
            "GPU / aceleradores de IA: NVIDIA, AMD",
            "ASIC custom & networking: Broadcom, Marvell, Astera Labs, Credo",
            "Memória: Micron",
            "Foundry: TSMC, Intel, GlobalFoundries",
            "Equipamentos: ASML, Applied Materials, Lam Research, KLA, Teradyne",
            "Analógico / mobile: Qualcomm, Analog Devices, Texas Instruments, NXP, ARM",
        ],
    },
    "DRAM": {
        "name": "Roundhill Memory ETF",
        "listing": "DRAM US · Cboe BZX · USD",
        "index": "Gestão ativa (sem índice)",
        "camada": "Memória (DRAM/HBM/NAND) e storage",
        "estrategia": (
            "ETF ativo, lançado em 01/04/2026, concentrado em fabricantes de memória. Usa swaps "
            "para acessar ações de difícil acesso direto (Micron, Samsung, SK hynix, CXMT); por isso "
            "~37% do patrimônio fica em T-Bills/caixa como colateral. Na look-through tratamos swap "
            "como exposição à ação subjacente. HBM é o gargalo de memória dos aceleradores de IA."
        ),
        "ecossistema": [
            "DRAM / HBM: Samsung, SK hynix, Micron, CXMT (China, via swap), Nanya, Winbond",
            "NAND / flash: SanDisk, Kioxia, GigaDevice",
            "HDD / storage: Seagate, Western Digital",
        ],
    },
    "GRDU": {
        "name": "First Trust Nasdaq Clean Edge Smart Grid Infrastructure UCITS ETF",
        "listing": "GRDU LN · LSE · USD · UCITS (Irlanda)",
        "index": "Nasdaq OMX Clean Edge Smart Grid Infrastructure Exclusions Index",
        "camada": "Energia: rede elétrica e eletrificação",
        "estrategia": (
            "Replica índice de empresas de rede elétrica, medição inteligente, armazenamento e "
            "software de gestão de energia. Data centers de IA são intensivos em energia; o gargalo "
            "de conexão à rede e de equipamentos elétricos sustenta a tese."
        ),
        "ecossistema": [
            "Equipamentos elétricos: Eaton, ABB, Schneider, Hubbell, nVent, GE Vernova, HD Hyundai Electric, LS Electric",
            "Climatização & automação predial: Johnson Controls, Belimo",
            "EPC / engenharia de rede: Quanta Services, SPIE",
            "Cabos: Prysmian, NKT",
            "Transmissão / utilities: National Grid, Terna, Hydro One, Equatorial",
        ],
    },
}

# ── Dados Morningstar (morningstar_data.json) ──
# Gerado/atualizado por refresh_morningstar.py a partir das respostas do Morningstar MCP:
#   etf               — Data Tool nível ETF (ver ETF_DATAPOINTS em refresh_morningstar.py);
#                       idx_mo_end / idx_ref = Daily Return Index (HS793) no último fechamento
#                       mensal e na data de referência → MTD
#   dram_return_index — HS793 diário do DRAM desde o lançamento (retorno e vol desde o início)
#   stocks            — Data Tool nível ação (ver STOCK_DATAPOINTS)
#   holdings / xray   — Fund Holdings Tool (top 25) e X-Ray da carteira
#   fx_per_usd        — unidades de moeda local por 1 USD (market cap das ações fora dos EUA)
#   usdbrl_ptax       — PTAX venda (Banco Central) no fim de cada ano e na data mais recente
MS_DATA_FILE = os.path.join(SCRIPT_DIR, "morningstar_data.json")
with open(MS_DATA_FILE, encoding="utf-8") as _f:
    MS = json.load(_f)

REF_DATE = MS["ref_date"]            # Return Date (Daily) Morningstar
MO_END_DATE = MS["mo_end_date"]      # Return Date (Mo-End) — base do MTD, 2A, 3A e vol 12m
HOLDINGS_DATE = MS["holdings_date"]  # data do portfólio dos ETFs
MS_ETF = MS["etf"]
# DRAM: dias sem negociação (valor repetido) são descartados antes dos retornos diários.
DRAM_RETURN_INDEX = [v for _, v in sorted(MS["dram_return_index"].items())]
XRAY = MS["xray"]
HOLDINGS = {k: [tuple(h) for h in v] for k, v in MS["holdings"].items()}
FX_PER_USD = MS["fx_per_usd"]
USDBRL_PTAX = {(int(k) if k.isdigit() else k): v for k, v in MS["usdbrl_ptax"].items()}
STOCKS = MS["stocks"]

# ── Entrada de cada tema na carteira TAG: Daily Return Index (HS793) no fechamento da data ──
# Retorno desde a entrada = índice em REF_DATE ÷ índice na data de entrada − 1 (USD, total return).
# CSPX (núcleo) sem data de entrada informada; CSPX_AT_ENTRY = índice do CSPX nas mesmas datas,
# para comparar cada tema com o S&P 500 no mesmo período.
CSPX_AT_ENTRY = {"2025-09-01": 689.77460, "2026-01-07": 741.58540, "2026-08-03": 818.55180}
ENTRY = {
    "CIBR": ("2025-09-01", 77.31617),
    "BKCH": ("2026-01-07", 85.75699),
    "BRIJ": ("2026-01-07", 23.12044),
    "SOXQ": ("2026-08-03", 94.15250),
    "DRAM": ("2026-08-03", 51.04400),
    "GRDU": ("2026-08-03", 63.04600),
}

# ── Retorno por ano-calendário: Daily Return Index (HS793) no último dia de cada ano ──
# (Morningstar; fins de semana/feriados repetem o último pregão). None = ETF ainda não existia.
# Ano parcial de lançamento (BRIJ 2024, GRDU 2022) fica em branco; DRAM 2026 = desde o início.
YEAR_END_INDEX = {
    #        2021-12-31  2022-12-31  2023-12-31  2024-12-31  2025-12-31
    "CSPX": (486.51790, 397.24380, 500.19310, 623.67180, 733.32100),
    "CIBR": (55.03338, 40.52761, 56.41080, 66.93674, 75.70120),
    "BKCH": (91.14712, 13.46298, 49.94033, 59.19177, 75.32183),
    "BRIJ": (None, None, None, 15.20826, 21.99706),
    "SOXQ": (31.30005, 20.34144, 33.90375, 40.70264, 58.23536),
    "DRAM": (None, None, None, None, None),
    "GRDU": (None, 29.33100, 35.50900, 40.95100, 53.00800),
}
CAL_YEARS = [2026, 2025, 2024, 2023, 2022]

# Nome consolidado para a look-through (classes de ação / ADR / preferencial → mesma empresa)
ISSUER_ALIAS = {"0P00012BBI": "0P000002HD"}  # Alphabet C → Alphabet A
ISSUER_NAME = {
    "0P000002HD": "Alphabet (A+C)", "0P000003MC": "Micron Technology", "0P0000B2XZ": "Samsung Electronics",
    "0P0000AZ1B": "SK hynix", "CXMT": "CXMT (ChangXin Memory, via swap)",
}

# P/E TTM acima de 200x ou negativo = sem significado econômico → exibido como "n.s."
PE_CAP = 200.0

ETF_ORDER = [k for k, _, _ in PORTFOLIO]
WEIGHTS = {k: w for k, w, _ in PORTFOLIO}
MS_IDS = {k: m for k, _, m in PORTFOLIO}


def _r(x, n=2):
    return None if x is None else round(x, n)


def dram_inception_stats():
    idx = DRAM_RETURN_INDEX
    traded = [idx[0]] + [b for a, b in zip(idx, idx[1:]) if b != a]
    rets = [b / a - 1 for a, b in zip(traded, traded[1:])]
    mean = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1))
    return {"since_inception": (idx[-1] / idx[0] - 1) * 100, "vol_inception": sd * math.sqrt(252) * 100,
            "n_days": len(rets)}


def build_etfs():
    dram = dram_inception_stats()
    etfs = []
    for key in ETF_ORDER:
        d = dict(MS_ETF[key])
        mtd = (d["idx_ref"] / d["idx_mo_end"] - 1) * 100
        row = {
            "key": key, "ms_id": MS_IDS[key], "weight": WEIGHTS[key], **ETF_INFO[key],
            "price": d["price"], "cur": d["cur"], "aum_usd_bn": d["aum"] / 1e9,
            "avg_mcap_usd_bn": d["avg_mcap"] / 1e3,
            "r1d": d["r1d"], "mtd": mtd, "ytd": d["ytd"], "r1y": d["r1y"], "r2y": d["r2y"], "r3y": d["r3y"],
            "vol1y": d["vol1y"], "pe": d["pe"], "fpe": d["fpe"], "pb": d["pb"], "fpb": d["fpb"], "roe": d["roe"],
            "dy": d["dy"] * 100, "ps": d["ps"], "pcf": d["pcf"], "debt_cap": d["debt_cap"],
            "net_margin": d["net_margin"], "eg_lt": d["eg_lt"], "eg_hist": d["eg_hist"], "ter": d["ter"],
            "n_stocks": d["n_stocks"], "inception": d["inception"], "category": d["category"],
            "since_inception": d.get("since_inception"), "vol_note": None,
            "entry_date": ENTRY.get(key, (None,))[0],
            "since_entry": (d["idx_ref"] / ENTRY[key][1] - 1) * 100 if key in ENTRY else None,
            "cspx_since_entry": (MS_ETF["CSPX"]["idx_ref"] / CSPX_AT_ENTRY[ENTRY[key][0]] - 1) * 100
                                if key in ENTRY else None,
        }
        if key == "DRAM":
            row["since_inception"] = dram["since_inception"]
            row["vol1y"] = dram["vol_inception"]
            row["vol_note"] = f"desde o início (01/04/2026, {dram['n_days']} pregões)"
        etfs.append(row)
    return etfs


def _harmonic(pairs):
    """Média harmônica ponderada (padrão para múltiplos de carteira): 1 / Σ w·(1/x)."""
    pairs = [(w, x) for w, x in pairs if x not in (None, 0) and x > 0]
    tw = sum(w for w, _ in pairs)
    return (tw / sum(w / x for w, x in pairs), tw) if pairs else (None, 0)


def _arith(pairs):
    pairs = [(w, x) for w, x in pairs if x is not None]
    tw = sum(w for w, _ in pairs)
    return (sum(w * x for w, x in pairs) / tw, tw) if pairs else (None, 0)


def build_portfolio(etfs):
    w = {e["key"]: e["weight"] / 100 for e in etfs}
    out = {}
    for f in ("r1d", "mtd", "ytd", "r1y", "r2y", "r3y"):
        v, cov = _arith([(w[e["key"]], e[f]) for e in etfs])
        out[f] = v
        out[f + "_cov"] = cov * 100
    for f in ("pe", "fpe", "pb", "fpb", "ps", "pcf"):
        v, cov = _harmonic([(w[e["key"]], e[f]) for e in etfs])
        out[f] = v
        out[f + "_cov"] = cov * 100
    for f in ("roe", "dy", "net_margin", "debt_cap", "eg_lt", "ter"):
        v, cov = _arith([(w[e["key"]], e[f]) for e in etfs])
        out[f] = v
        out[f + "_cov"] = cov * 100
    return out


def stock_row(ms_id):
    s = STOCKS.get(ms_id)
    if not s:
        return None
    fx = FX_PER_USD[s["cur"]]
    pe = s["pe"] if s["pe"] is not None and 0 < s["pe"] <= PE_CAP else None
    return {
        "ticker": s["ticker"], "country": s["country"], "sector": s["sector"], "cur": s["cur"],
        "price": s["price"], "mcap_usd_bn": s["mcap"] / fx / 1e3,
        "r1d": s["r1d"], "ytd": s["ytd"], "r1y": s["r1y"],
        "pe": pe, "pe_ns": s["pe"] is not None and pe is None, "fpe": s["fpe"], "pb": s["pb"],
        "roe": None if s["roe"] is None else s["roe"] * 100,
        "dy": None if s["dy"] is None else s["dy"] * 100, "pfv": s["pfv"], "moat": s["moat"],
    }


def build_top10():
    top = {}
    for key in ETF_ORDER:
        rows = []
        for name, wgt, ms_id in HOLDINGS[key]:
            if ms_id == "CASH":
                continue
            rows.append({"name": name, "weight": wgt, "ms_id": ms_id, **(stock_row(ms_id) or {})})
        # DRAM: consolida posição direta + swaps na mesma empresa antes de pegar o top 10
        if key == "DRAM":
            agg = {}
            for r in rows:
                k = r["ms_id"]
                if k not in agg:
                    agg[k] = dict(r, name=ISSUER_NAME.get(k, r["name"]), weight=0.0)
                agg[k]["weight"] += r["weight"]
            rows = sorted(agg.values(), key=lambda r: -r["weight"])
        top[key] = rows[:10]
    return top


def build_lookthrough():
    agg = {}
    for key in ETF_ORDER:
        wf = WEIGHTS[key] / 100
        for name, wgt, ms_id in HOLDINGS[key]:
            if ms_id == "CASH":
                continue
            issuer = ISSUER_ALIAS.get(ms_id, ms_id)
            a = agg.setdefault(issuer, {"ms_id": issuer, "name": ISSUER_NAME.get(issuer, name),
                                        "weight": 0.0, "sources": {}})
            a["weight"] += wf * wgt
            a["sources"][key] = a["sources"].get(key, 0.0) + wf * wgt
    rows = sorted(agg.values(), key=lambda r: -r["weight"])
    out = []
    for r in rows[:25]:
        r.update(stock_row(r["ms_id"]) or {})
        r["sources"] = {k: round(v, 3) for k, v in sorted(r["sources"].items(), key=lambda kv: -kv[1])}
        out.append(r)
    top10_w = sum(r["weight"] for r in out[:10])
    # Múltiplos agregados das 10 maiores posições (média harmônica ponderada)
    t10 = out[:10]
    agg10 = {
        "weight": top10_w,
        "pe": _harmonic([(r["weight"], r.get("pe")) for r in t10])[0],
        "fpe": _harmonic([(r["weight"], r.get("fpe")) for r in t10])[0],
        "pb": _harmonic([(r["weight"], r.get("pb")) for r in t10])[0],
        "roe": _arith([(r["weight"], r.get("roe")) for r in t10])[0],
        "dy": _arith([(r["weight"], r.get("dy")) for r in t10])[0],
        "pfv": _arith([(r["weight"], r.get("pfv")) for r in t10])[0],
    }
    return out, agg10


def build_entry_summary(etfs):
    """Média dos temas desde a entrada, ponderada pelo peso de cada tema na carteira TAG,
    vs. o CSPX (S&P 500) nas mesmas janelas. excess_total = Σ peso × (tema − CSPX), em p.p. da
    carteira inteira: quanto os temas somaram/tiraram vs. ter esse capital no S&P 500."""
    th = [e for e in etfs if e.get("since_entry") is not None]
    tw = sum(e["weight"] for e in th)
    avg = sum(e["weight"] * e["since_entry"] for e in th) / tw
    avg_cspx = sum(e["weight"] * e["cspx_since_entry"] for e in th) / tw
    excess_total = sum(e["weight"] / 100 * (e["since_entry"] - e["cspx_since_entry"]) for e in th)
    return {"weight": tw, "avg": avg, "avg_cspx": avg_cspx, "diff": avg - avg_cspx,
            "excess_total": excess_total, "n": len(th)}


def build_calendar(etfs):
    """Retorno total em USD por ano-calendário (2026 = YTD até REF_DATE) + USD/BRL."""
    by_key = {e["key"]: e for e in etfs}
    rows = []
    for key in ETF_ORDER:
        idx = dict(zip([2021, 2022, 2023, 2024, 2025], YEAR_END_INDEX[key]))
        idx[2026] = MS_ETF[key]["idx_ref"]
        rets, flags = {}, {}
        for y in CAL_YEARS:
            a, b = idx.get(y - 1), idx.get(y)
            rets[y] = (b / a - 1) * 100 if a and b else None
        if key == "DRAM":
            rets[2026] = by_key["DRAM"]["since_inception"]
            flags[2026] = "desde 01/04/2026"
        rows.append({"key": key, "weight": WEIGHTS[key], "returns": rets, "flags": flags})
    port, cov = {}, {}
    for y in CAL_YEARS:
        pairs = [(r["weight"], r["returns"][y]) for r in rows if r["returns"][y] is not None
                 and not r["flags"].get(y)]
        tw = sum(w for w, _ in pairs)
        port[y] = sum(w * v for w, v in pairs) / tw if tw else None
        cov[y] = tw
    fx = {}
    for y in CAL_YEARS:
        end = USDBRL_PTAX["ref"] if y == 2026 else USDBRL_PTAX[y]
        fx[y] = (end / USDBRL_PTAX[y - 1] - 1) * 100
    port_brl = {y: None if port[y] is None else ((1 + port[y] / 100) * (1 + fx[y] / 100) - 1) * 100
                for y in CAL_YEARS}
    return {"years": CAL_YEARS, "rows": rows, "portfolio": port, "portfolio_cov": cov,
            "usdbrl": fx, "usdbrl_levels": {str(k): v for k, v in USDBRL_PTAX.items()},
            "portfolio_brl": port_brl}


def main():
    etfs = build_etfs()
    port = build_portfolio(etfs)
    calendar = build_calendar(etfs)
    top10 = build_top10()
    look, agg10 = build_lookthrough()

    def clean(o):
        if isinstance(o, float):
            return round(o, 4)
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o

    data = {
        "title": "Monitor de ETFs — Carteira de Bolsa TAG (Ecossistema AI)",
        "reference_date": REF_DATE, "mo_end_date": MO_END_DATE, "holdings_date": HOLDINGS_DATE,
        "source": f"Morningstar MCP (Data Tool, Fund Holdings, X-Ray) · câmbio: fontes públicas "
                  f"{'/'.join(reversed(MS['fx_date'].split('-')))}",
        "fx_per_usd": FX_PER_USD, "fx_date": MS["fx_date"], "usdbrl_ref_date": MS["usdbrl_ptax_ref_date"],
        "etfs": etfs, "portfolio": port, "entry_summary": build_entry_summary(etfs), "calendar": calendar, "xray": XRAY,
        "top10": top10, "lookthrough": look, "lookthrough_top10": agg10,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(clean(data), f, ensure_ascii=False, indent=2)
    print(f"OK → {OUT}")
    for e in etfs:
        print(f"  {e['key']:5} peso {e['weight']:5.1f}%  MTD {e['mtd']:6.2f}%  vol {e['vol1y'] or 0:6.2f}")
    print("  Top 10 TAG:", ", ".join(f"{r['name']} {r['weight']:.2f}%" for r in look[:10]))


if __name__ == "__main__":
    main()
