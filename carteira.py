"""
carteira.py — configuração da carteira TAG e regras de tratamento das holdings, compartilhadas por
build_tag_equities.py (gera o JSON do app) e refresh_morningstar.py (atualiza os dados Morningstar).
"""
import re

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
ETF_ORDER = [k for k, _, _ in PORTFOLIO]
WEIGHTS = {k: w for k, w, _ in PORTFOLIO}
MS_IDS = {k: m for k, _, m in PORTFOLIO}

# Nome consolidado para a look-through (classes de ação / ADR / preferencial → mesma empresa)
ISSUER_ALIAS = {
    "0P00012BBI": "0P000002HD",   # Alphabet C → Alphabet A
    "0P00035YJ3": "0P0000AZ1B",   # SK hynix ADR → SK hynix
    "0P0000D5B8": "0P0000B2XZ",   # Samsung preferencial → Samsung
}
ISSUER_NAME = {
    "0P000002HD": "Alphabet (A+C)", "0P000003MC": "Micron Technology", "0P0000B2XZ": "Samsung Electronics",
    "0P0000AZ1B": "SK hynix", "CXMT": "CXMT (ChangXin Memory, via swap)",
}

# Swaps do DRAM vêm sem Morningstar ID: exposição econômica = ação subjacente
SWAP_UNDERLYING = {"MICRON": "0P000003MC", "SAMSUNG": "0P0000B2XZ", "SK HYNIX": "0P0000AZ1B", "CXMT": "CXMT"}
_CURRENCY_WORDS = ("DOLLAR", "WON", "EURO", "YEN", "POUND", "YUAN", "RENMINBI", "FRANC", "KRONE", "CASH")


_NAME_NOISE = [
    r"\s+Ordinary Shares(\s*-\s*New)?", r"\s+Az nom Post raggruppamento", r"\s+Act\. Provenant Regroupement",
    r"\s+Bearer and\s*/\s*or registered shares", r"\s+Registered Shares", r"\s+Pfd Registered Shs Non-Voting",
]


def clean_name(name):
    for pat in _NAME_NOISE:
        name = re.sub(pat, "", name, flags=re.I)
    name = re.sub(r"\s*-\s*Class", " Class", name)
    return re.sub(r"\s+", " ", name).strip()


def classify_holding(ms_id, name, weight):
    """Holding bruta do Fund Holdings Tool → (nome, peso, ms_id | "CASH" | "CXMT" | None)."""
    up = name.upper()
    if not ms_id and "SWAP" in up:
        for key, under in SWAP_UNDERLYING.items():
            if key in up:
                broker = " Goldman" if "GOLD" in up else ""
                base = ISSUER_NAME.get(under, key.title()).split(" (")[0]
                return (f"{base} (swap{broker})", weight, under)
        return (clean_name(name), weight, None)
    if not ms_id and any(w in up for w in _CURRENCY_WORDS):
        return (clean_name(name), weight, "CASH")
    if ms_id and ms_id[0] in "FB":   # fundos monetários (F…) e T-Bills/títulos (B…)
        return (clean_name(name), weight, "CASH")
    return (clean_name(name), weight, ms_id or None)


def needed_stock_ids(holdings, top=10, look=25):
    """IDs das ações que o app mostra: top 10 de cada ETF (DRAM consolidado por empresa) e as
    `look` maiores posições da carteira look-through."""
    need, agg = set(), {}
    for key, rows in holdings.items():
        rows = [r for r in rows if r[2] != "CASH"]
        for _, wgt, ms_id in rows:
            if ms_id:
                issuer = ISSUER_ALIAS.get(ms_id, ms_id)
                agg[issuer] = agg.get(issuer, 0.0) + WEIGHTS[key] / 100 * wgt
        if key == "DRAM":
            rows = dram_consolidated(rows)
        need.update(r[2] for r in rows[:top])
    need.update(sorted(agg, key=lambda k: -agg[k])[:look])
    return sorted(i for i in need if i and i.startswith("0P"))


def dram_consolidated(rows):
    """DRAM: posição direta + swaps (+ ADR/preferencial) somados por empresa, maior peso primeiro."""
    agg = {}
    for name, wgt, ms_id in rows:
        k = ISSUER_ALIAS.get(ms_id, ms_id) if ms_id else name
        if k not in agg:
            agg[k] = [ISSUER_NAME.get(k, name), 0.0, ms_id and k]
        agg[k][1] += wgt
    return sorted((tuple(v) for v in agg.values()), key=lambda r: -r[1])
