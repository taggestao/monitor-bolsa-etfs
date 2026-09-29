# Monitor de Bolsa — ETFs TAG (Ecossistema AI)

Streamlit app that tracks the TAG equity portfolio:

| ETF | Weight | Layer |
|---|---|---|
| CSPX LN | 50,0% | Core S&P 500 |
| CIBR US | 10,0% | Cybersecurity |
| BKCH US | 10,0% | Crypto + HPC/AI data centers |
| BRIJ LN | 10,0% | European infrastructure |
| SOXQ US | 6,6% | Semiconductors |
| DRAM US | 6,6% | Memory (DRAM/HBM/NAND) |
| GRDU LN | 6,8% | Power grid |

Tabs: **Visão Geral** (price, AUM, returns for the day/MTD/YTD/12M/24M/36M, 12M vol, valuation), **Estratégia & Ecossistema**, **Top 10 por ETF** (per-stock valuation) and **Carteira TAG** (look-through of positions, sectors vs. S&P 500).

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Go to https://share.streamlit.io and sign in with the GitHub account `taggestao`.
2. On the first login, authorize Streamlit to access **private** repositories
   (Settings → Linked accounts → GitHub → *Authorize private repos*).
3. **Create app** → *Deploy a public app from GitHub* and fill in:
   - Repository: `taggestao/monitor-bolsa-etfs`
   - Branch: `main`
   - Main file path: `app.py`
   - App URL (optional): e.g. `tag-monitor-bolsa`
4. *Advanced settings* → Python **3.11**. No secrets needed (the data are in `tag_equities.json`).
5. **Deploy**. Every push to `main` redeploys the app automatically.

Private repo → the app is private by default: share it under *Settings → Sharing* with the TAG
team's emails (or make it public, if appropriate).

## Updating the data

The data come from Morningstar (MCP) and are hard-coded in `build_tag_equities.py`
(dicts `MS_ETF`, `HOLDINGS`, `STOCKS`, `XRAY`, `FX_PER_USD`). After re-collecting them (or changing
the weights in `PORTFOLIO`), regenerate the JSON the app reads:

```bash
python build_tag_equities.py   # → tag_equities.json
```
