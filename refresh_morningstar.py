"""
refresh_morningstar.py — atualiza morningstar_data.json com respostas do Morningstar MCP.

O app (Streamlit Cloud) não acessa o Morningstar MCP diretamente; a coleta é feita por uma
sessão do Claude com o conector Morningstar (rotina diária — ver ATUALIZACAO.md):

  1. python refresh_morningstar.py --plan
       → imprime as chamadas ao morningstar-data-tool necessárias (IDs, datapoints, datas).
  2. Salvar cada resposta do MCP como um .json em uma pasta (ex.: raw/): a resposta original
     ({"result": {...}}) ou o formato compacto {ms_id: {datapoint: valor}}, com séries
     históricas como {ms_id: {"HS793": {"AAAA-MM-DD": valor}}}.
  3. python refresh_morningstar.py raw/ [--ptax 5.1234 --ptax-date AAAA-MM-DD] [--fx EUR=0.86 ...]
       → atualiza morningstar_data.json (ETFs, índice diário, DRAM, ações, datas).
  4. python build_tag_equities.py  → tag_equities.json (lido pelo app).

Holdings e X-Ray mudam pouco (mensal) e continuam sendo atualizados à parte.
"""
import argparse, calendar, datetime as dt, glob, json, os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "morningstar_data.json")

ETF_IDS = {
    "CSPX": "0P0000SM09", "CIBR": "F00000VWQP", "BKCH": "F000016SOI", "BRIJ": "0P0001TOAU",
    "SOXQ": "F000016Y1C", "DRAM": "F00001TGL6", "GRDU": "F00001DPBY",
}
# campo em morningstar_data.json → datapoint Morningstar (nível ETF)
ETF_DATAPOINTS = {
    "price": "OS065", "aum": "OF99A", "avg_mcap": "HS03W", "r1d": "PD003", "ytd": "PD00B",
    "ytd_m": "PM00A", "r1y": "PD00D", "r2y": "PD014", "r3y": "PD00F", "vol1y": "RR014",
    "pe": "HS05X", "fpe": "HS067", "pb": "HS05V", "fpb": "HS064", "roe": "HS08F", "dy": "DC252",
    "ps": "HS05U", "pcf": "HS05W", "debt_cap": "HS06U", "net_margin": "HS08D", "eg_lt": "HS031",
    "eg_hist": "HS034", "ter": "OS05P", "n_stocks": "HS073",
}
# nível ação (mcap e preço em moeda local; roe e dy em fração)
STOCK_DATAPOINTS = {
    "mcap": "ST159", "price": "ST157", "r1d": "PD003", "ytd": "PD00B", "r1y": "PD00D",
    "pe": "ST412", "fpe": "ST198", "pb": "ST408", "roe": "ZUPRD", "dy": "EQCUJ", "pfv": "OS603",
    "moat": "LT181",
}
RETURN_INDEX = "HS793"   # Daily Return Index (série diária, inclui fins de semana)
STOCK_BATCH = 10


def _month_end_before(d):
    first = d.replace(day=1)
    return first - dt.timedelta(days=1)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def plan(data):
    today = dt.date.today()
    mo_end = _month_end_before(today - dt.timedelta(days=1))
    dram_last = max(data["dram_return_index"])
    stocks = sorted(data["stocks"])
    calls = [
        {"file": "etf_snapshot.json", "investment_ids": list(ETF_IDS.values()),
         "datapoint_ids": list(ETF_DATAPOINTS.values())},
        {"file": "etf_index.json", "investment_ids": list(ETF_IDS.values()),
         "datapoint_ids": [RETURN_INDEX], "start_date": mo_end.isoformat(), "end_date": today.isoformat()},
        {"file": "dram_index.json", "investment_ids": [ETF_IDS["DRAM"]], "datapoint_ids": [RETURN_INDEX],
         "start_date": dram_last, "end_date": today.isoformat()},
    ]
    for i in range(0, len(stocks), STOCK_BATCH):
        calls.append({"file": f"stocks_{i // STOCK_BATCH + 1:02d}.json",
                      "investment_ids": stocks[i:i + STOCK_BATCH],
                      "datapoint_ids": list(STOCK_DATAPOINTS.values())})
    print(json.dumps(calls, indent=1))


def load_responses(raw_dir):
    """Junta todas as respostas do morningstar-data-tool salvas em raw_dir.
    → snap[ms_id][datapoint] = value/code ; series[ms_id][datapoint][date] = float"""
    snap, series = {}, {}
    files = sorted(glob.glob(os.path.join(raw_dir, "*.json")))
    if not files:
        sys.exit(f"Nenhum .json em {raw_dir}")
    for fn in files:
        with open(fn, encoding="utf-8") as f:
            resp = json.load(f)
        for ms_id, body in resp.get("result", resp).items():
            if "values" not in body:
                # formato compacto: {ms_id: {datapoint: valor | {data: valor}}}
                for dp, v in body.items():
                    if isinstance(v, dict):
                        s = series.setdefault(ms_id, {}).setdefault(dp, {})
                        s.update({d: float(x) for d, x in v.items() if _num(x) is not None})
                    else:
                        snap.setdefault(ms_id, {})[dp] = v
                continue
            for v in body["values"]:
                dp = v["datapointId"]
                if "timeSeriesData" in v:
                    s = series.setdefault(ms_id, {}).setdefault(dp, {})
                    for p in v["timeSeriesData"]:
                        if _num(p.get("value")) is not None:
                            s[p["date"]] = float(p["value"])
                else:
                    snap.setdefault(ms_id, {})[dp] = v.get("code") if dp == "LT181" else v.get("value")
    return snap, series


def _value_at(s, day):
    """Último valor da série em ou antes de `day` (AAAA-MM-DD)."""
    keys = [k for k in s if k <= day]
    return s[max(keys)] if keys else None


def apply(data, snap, series, args):
    log = []
    # ── Data de referência = último dia útil com índice diário do CSPX ──
    cspx = series.get(ETF_IDS["CSPX"], {}).get(RETURN_INDEX)
    if not cspx:
        sys.exit("Faltou a série HS793 do CSPX (etf_index.json).")
    ref = max(d for d in cspx if dt.date.fromisoformat(d).weekday() < 5)
    if ref < data["ref_date"]:
        sys.exit(f"Dados recebidos ({ref}) são mais antigos que os atuais ({data['ref_date']}).")
    mo_end = _month_end_before(dt.date.fromisoformat(ref)).isoformat()

    # ── ETFs ──
    for key, ms_id in ETF_IDS.items():
        e = data["etf"][key]
        s = snap.get(ms_id)
        if not s or s.get("OS065") is None:
            sys.exit(f"Faltou o snapshot do ETF {key} ({ms_id}).")
        for field, dp in ETF_DATAPOINTS.items():
            v = _num(s.get(dp))
            if v is not None:   # datapoint ausente na resposta → mantém o valor anterior
                e[field] = int(v) if field == "n_stocks" else v
        idx = series.get(ms_id, {}).get(RETURN_INDEX, {})
        e["idx_ref"], e["idx_mo_end"] = _value_at(idx, ref), _value_at(idx, mo_end)
        if e["idx_ref"] is None or e["idx_mo_end"] is None:
            sys.exit(f"Série HS793 de {key} não cobre {mo_end} → {ref}.")
        log.append(f"{key}: preço {e['price']}  1D {e['r1d']}  MTD "
                   f"{(e['idx_ref'] / e['idx_mo_end'] - 1) * 100:.2f}%")

    # ── DRAM: série diária desde o lançamento (acrescenta datas novas até ref) ──
    dram = series.get(ETF_IDS["DRAM"], {}).get(RETURN_INDEX, {})
    new = {d: v for d, v in dram.items() if d <= ref}
    data["dram_return_index"].update(new)
    days = sorted(data["dram_return_index"])
    gaps = [b for a, b in zip(days, days[1:])
            if (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days != 1]
    if gaps or days[-1] != ref:
        sys.exit(f"Série do DRAM incompleta (lacunas em {gaps[:3]}, último dia {days[-1]}, ref {ref}).")

    # ── Ações ──
    updated, missing = 0, []
    for ms_id, st in data["stocks"].items():
        s = snap.get(ms_id)
        if not s or s.get("ST157") is None:
            missing.append(f"{st['ticker']} ({ms_id})")
            continue
        for field, dp in STOCK_DATAPOINTS.items():
            v = s.get(dp) if field == "moat" else _num(s.get(dp))
            if v is not None:   # datapoint ausente na resposta → mantém o valor anterior
                st[field] = v
        updated += 1
    log.append(f"Ações atualizadas: {updated}/{len(data['stocks'])}")
    if missing:
        log.append("  sem dados novos (mantidos os anteriores): " + ", ".join(missing))

    # ── Câmbio ──
    if args.ptax:
        data["usdbrl_ptax"]["ref"] = args.ptax
        data["usdbrl_ptax_ref_date"] = args.ptax_date or ref
        log.append(f"PTAX {args.ptax} em {data['usdbrl_ptax_ref_date']}")
    if args.fx:
        for item in args.fx:
            cur, val = item.split("=")
            data["fx_per_usd"][cur.upper()] = float(val)
        data["fx_date"] = args.fx_date or ref
        log.append(f"Câmbio atualizado em {data['fx_date']}: {', '.join(args.fx)}")

    data["ref_date"], data["mo_end_date"] = ref, mo_end
    log.insert(0, f"Data de referência {ref} · fechamento mensal {mo_end}")
    return log


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw_dir", nargs="?", help="pasta com as respostas do morningstar-data-tool (.json)")
    ap.add_argument("--plan", action="store_true", help="lista as chamadas ao MCP necessárias")
    ap.add_argument("--ptax", type=float, help="PTAX venda USD/BRL mais recente")
    ap.add_argument("--ptax-date", help="data da PTAX (AAAA-MM-DD)")
    ap.add_argument("--fx", nargs="*", help="moeda local por 1 USD, ex.: EUR=0.8612 KRW=1362.5")
    ap.add_argument("--fx-date", help="data das cotações de --fx (AAAA-MM-DD)")
    args = ap.parse_args()

    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)
    if args.plan:
        return plan(data)
    if not args.raw_dir:
        ap.error("informe raw_dir ou --plan")
    snap, series = load_responses(args.raw_dir)
    log = apply(data, snap, series, args)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("\n".join(log))
    print(f"OK → {DATA_FILE}")


if __name__ == "__main__":
    main()
