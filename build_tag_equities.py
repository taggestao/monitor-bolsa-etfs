"""
build_tag_equities.py — Monitor de ETFs da carteira de bolsa TAG (Ecossistema AI).

Processa os dados Morningstar coletados via MCP (Data Tool, Fund Holdings Tool e X-Ray
Portfolio Analysis) e gera tag_equities.json, consumido pelo app (app.py).
Executar a cada atualização dos dados (ou da alocação em PORTFOLIO).

Fontes:
  • Morningstar MCP — preço, AUM, retornos, vol, valuation dos ETFs e das ações, holdings,
    X-Ray da carteira (setores, P/E, P/B, ROE). Coleta em REF_DATE.
  • USD/BRL — PTAX venda do Banco Central no fim de cada ano e em 28/09/2026.
  • Câmbio (para converter market cap de ações fora dos EUA em USD) — cotações públicas de
    29/09/2026 (Trading Economics / exchangerates.org.uk / MTFX via busca web).
"""
import json, math, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(SCRIPT_DIR, "tag_equities.json")

REF_DATE = "2026-09-28"          # Return Date (Daily) Morningstar
MO_END_DATE = "2026-08-31"       # Return Date (Mo-End) — base do MTD, 2A, 3A e vol 12m
HOLDINGS_DATE = "2026-09-28"     # data do portfólio (DRAM 24/09, CSPX 25/09)

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

# ── Morningstar Data Tool — nível ETF (valores brutos em %, exceto onde indicado) ──
# OS065 preço · OF99A AUM USD · HS03W mkt cap médio (US$ mi) · PD003 1D · PD00B YTD(d) ·
# PM00A YTD(m) · PD00D 1A(d) · PD014 2A anualiz.(d) · PD00F 3A anualiz.(d) · RR014 vol 1A ·
# HS05X P/E TTM · HS067 P/E projetado · HS05V P/B TTM · HS064 P/B projetado · HS08F ROE ·
# DC252 div. yield (fração) · HS05U P/S · HS05W P/CF · HS06U dívida/capital · HS08D margem líq. ·
# HS031 cresc. LP lucro · HS034 cresc. hist. lucro · OS05P taxa · HS073 nº ações · OS00F início ·
# OF003 categoria · HS793 índice de retorno diário (31/08 e 28/09) → MTD
MS_ETF = {
    "CSPX": dict(price=828.66, cur="USD", aum=158112735900, avg_mcap=538856.69646, r1d=-0.77106,
                 ytd=13.01517, ytd_m=13.33580, r1y=16.73571, r2y=16.86895, r3y=22.63169, vol1y=13.125,
                 pe=25.07523, fpe=20.40268, pb=5.42711, fpb=4.66934, roe=37.83773, dy=0.01012,
                 ps=3.77173, pcf=19.33862, debt_cap=33.20236, net_margin=27.26639, eg_lt=16.65241,
                 eg_hist=10.93291, ter=0.07, n_stocks=504, inception="2010-05-19",
                 category="US Large-Cap Blend Equity", idx_0831=831.11520, idx_0928=828.76400),
    "CIBR": dict(price=101.67, cur="USD", aum=17081115990, avg_mcap=89299.38226, r1d=0.77335,
                 ytd=42.68759, ytd_m=40.36728, r1y=34.82187, r2y=31.47487, r3y=31.407, vol1y=35.878,
                 pe=33.47841, fpe=28.62113, pb=8.44737, fpb=7.1379, roe=22.28242, dy=0.00581,
                 ps=5.59347, pcf=22.82584, debt_cap=28.75887, net_margin=13.66543, eg_lt=12.00675,
                 eg_hist=9.77145, ter=0.58, n_stocks=45, inception="2015-07-06",
                 category="Technology", idx_0831=106.25972, idx_0928=108.01622),
    "BKCH": dict(price=72.24, cur="USD", aum=301162829, avg_mcap=8842.08325, r1d=-3.66017,
                 ytd=12.89919, ytd_m=9.04822, r1y=-7.19132, r2y=26.35764, r3y=50.94247, vol1y=75.439,
                 pe=None, fpe=18.28714, pb=2.78606, fpb=1.24506, roe=-21.49687, dy=0.00016,
                 ps=0.58617, pcf=None, debt_cap=39.56045, net_margin=None, eg_lt=13.66123,
                 eg_hist=52.87271, ter=0.50, n_stocks=33, inception="2021-07-12",
                 category="Equity Digital Assets", idx_0831=82.13711, idx_0928=85.03773),
    "BRIJ": dict(price=21.415, cur="EUR", aum=628396918, avg_mcap=18654.53393, r1d=-0.66712,
                 ytd=-2.53384, ytd_m=3.70622, r1y=0.64196, r2y=11.69906, r3y=None, vol1y=14.102,
                 pe=20.17349, fpe=16.76059, pb=2.18579, fpb=2.04751, roe=10.87899, dy=0.02858,
                 ps=1.1805, pcf=7.25584, debt_cap=38.53941, net_margin=8.09164, eg_lt=10.29306,
                 eg_hist=-3.35348, ter=0.47, n_stocks=48, inception="2024-09-03",
                 category="Sector Equity Infrastructure", idx_0831=22.80248, idx_0928=21.43968,
                 since_inception=17.88141),
    "SOXQ": dict(price=98.08, cur="USD", aum=3209583508, avg_mcap=371561.99107, r1d=-1.61484,
                 ytd=76.41964, ytd_m=63.16735, r1y=98.39329, r2y=55.34952, r3y=54.78674, vol1y=51.880,
                 pe=38.06624, fpe=21.62322, pb=10.3584, fpb=8.69928, roe=36.55786, dy=0.00525,
                 ps=11.7495, pcf=30.7787, debt_cap=21.8459, net_margin=31.37488, eg_lt=39.50578,
                 eg_hist=7.16493, ter=0.19, n_stocks=30, inception="2021-06-11",
                 category="Technology", idx_0831=95.02109, idx_0928=102.73861),
    "DRAM": dict(price=59.70, cur="USD", aum=25989651829, avg_mcap=493750.16797, r1d=-3.63022,
                 ytd=None, ytd_m=None, r1y=None, r2y=None, r3y=None, vol1y=None,
                 pe=12.03949, fpe=6.06861, pb=4.88281, fpb=3.24903, roe=55.48498, dy=0.00207,
                 ps=5.83669, pcf=12.05836, debt_cap=11.77171, net_margin=49.14969, eg_lt=51.41733,
                 eg_hist=53.71585, ter=0.65, n_stocks=15, inception="2026-04-01",
                 category="Technology", idx_0831=57.09500, idx_0928=59.83850,
                 since_inception=None, r3m=-16.91532),
    "GRDU": dict(price=61.71, cur="USD", aum=2856411641, avg_mcap=66207.72161, r1d=-1.02557,
                 ytd=16.70125, ytd_m=16.90311, r1y=20.4318, r2y=18.90485, r3y=24.84752, vol1y=25.907,
                 pe=31.2989, fpe=24.48982, pb=4.72233, fpb=4.36155, roe=21.82707, dy=0.01379,
                 ps=3.07844, pcf=19.33114, debt_cap=36.86367, net_margin=13.66967, eg_lt=13.00963,
                 eg_hist=11.69699, ter=None, n_stocks=108, inception="2022-04-14",
                 category="Sector Equity Infrastructure", idx_0831=61.96800, idx_0928=61.86100),
}

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

# ── USD/BRL — PTAX venda (Banco Central) no último dia útil de cada ano e na data de referência ──
USDBRL_PTAX = {2021: 5.5805, 2022: 5.2177, 2023: 4.8413, 2024: 6.1923, 2025: 5.5024, "ref": 5.2132}

# DRAM: Daily Return Index (HS793) desde o lançamento — usado para retorno desde o início e
# vol anualizada desde o início (fundo não tem 12 meses de histórico). Dias sem negociação
# (valor repetido) são descartados antes de calcular os retornos diários.
DRAM_RETURN_INDEX = [
    28.24000, 27.20980, 27.20980, 27.20980, 27.20980, 28.64800, 29.07290, 31.80130, 31.72420, 32.26080,
    32.26080, 32.26080, 32.60770, 34.43880, 34.39480, 34.97980, 34.44800, 34.44800, 34.44800, 34.55420,
    35.61620, 36.51420, 36.58350, 36.65690, 36.65690, 36.65690, 38.42790, 37.89040, 38.54820, 38.44390,
    39.14540, 39.14540, 39.14540, 41.94390, 43.77460, 47.10460, 47.63940, 49.99370, 49.99370, 49.99370,
    53.54000, 51.90210, 54.15520, 53.92730, 50.22770, 50.22770, 50.22770, 50.02140, 48.95770, 49.77140,
    53.61900, 53.16130, 53.16130, 53.16130, 53.16130, 57.98830, 60.54020, 60.64890, 63.00450, 63.00450,
    63.00450, 66.66640, 67.96560, 68.53760, 65.58940, 59.28930, 59.28930, 59.28930, 58.29710, 61.98610,
    58.15970, 61.42820, 63.75660, 63.75660, 63.75660, 69.19480, 69.27800, 71.18870, 75.25290, 75.25290,
    75.25290, 75.25290, 79.02580, 69.32380, 70.04950, 77.58220, 72.02110, 72.02110, 72.02110, 71.32480,
    72.37850, 67.48400, 60.83420, 60.83420, 60.83420, 60.83420, 64.63870, 60.72850, 59.82710, 62.17350,
    62.40370, 62.40370, 62.40370, 56.44840, 58.82000, 59.44900, 54.09000, 53.36530, 53.36530, 53.36530,
    52.49630, 57.08020, 57.21340, 58.91530, 54.53270, 54.53270, 54.53270, 54.34260, 48.00900, 44.76630,
    47.47720, 53.09710, 53.09710, 53.09710, 51.04400, 52.81200, 53.80170, 50.93040, 50.15240, 50.15240,
    50.15240, 49.98470, 50.71010, 53.42700, 56.00320, 57.74350, 57.74350, 57.74350, 59.52630, 57.13490,
    54.01680, 57.76100, 58.72670, 58.72670, 58.72670, 55.39320, 55.89920, 56.49200, 57.40480, 56.15140,
    56.15140, 56.15140, 57.09500, 56.61490, 55.71720, 55.62200, 58.10700, 58.10700, 58.10700, 58.10700,
    60.62460, 61.61200, 60.42170, 58.81050, 58.81050, 58.81050, 55.80760, 55.31310, 56.10370, 56.59140,
    59.47580, 59.47580, 59.47580, 60.79330, 62.43610, 62.74520, 60.93920, 62.09260, 62.09260, 62.09260,
    59.83850,
]

# ── X-Ray da carteira TAG (Morningstar Portfolio Analysis, 29/09/2026) ──
XRAY = {
    "as_of": "2026-08-31",
    "price_ratios": {"portfolio": {"pe": 24.79, "pb": 4.54, "ps": 2.21, "pcf": 16.46},
                     "benchmark": {"pe": 24.79, "pb": 5.28, "ps": 3.66, "pcf": 19.01}},
    "profitability": {"portfolio": {"roe": 26.96, "roa": 13.97, "net_margin": 23.85, "debt_capital": 32.51},
                      "benchmark": {"roe": 37.67, "roa": 19.93, "net_margin": 27.15, "debt_capital": 33.74}},
    "sectors": {  # % do patrimônio em ações (carteira vs. S&P 500)
        "Tecnologia": (44.21, 38.70), "Industriais": (15.76, 7.75), "Financeiro": (14.22, 12.06),
        "Comunicação": (5.99, 9.50), "Saúde": (4.75, 9.28), "Consumo cíclico": (4.66, 9.31),
        "Utilities": (3.23, 1.98), "Consumo defensivo": (2.23, 4.46), "Materiais básicos": (1.90, 1.68),
        "Energia": (1.73, 3.48), "Imobiliário": (1.32, 1.80),
    },
}

# ── Holdings (Morningstar Fund Holdings Tool, top 25 por ETF, % do patrimônio) ──
# (nome, peso, ms_id | None). Swaps do DRAM trazem o ms_id da ação subjacente (exposição econômica).
HOLDINGS = {
    "CSPX": [
        ("NVIDIA Corp", 8.14414, "0P000003RE"), ("Apple Inc", 7.44336, "0P000000GY"),
        ("Microsoft Corp", 5.73164, "0P000003MH"), ("Amazon.com Inc", 3.66419, "0P000000B7"),
        ("Alphabet Inc Class A", 3.01776, "0P000002HD"), ("Broadcom Inc", 2.50994, "0P0000KU35"),
        ("Meta Platforms Inc Class A", 2.47806, "0P0000W3KZ"), ("Alphabet Inc Class C", 2.42427, "0P00012BBI"),
        ("Micron Technology Inc", 1.82739, "0P000003MC"), ("Tesla Inc", 1.56783, "0P0000OQN8"),
        ("Advanced Micro Devices Inc", 1.53912, "0P0000006A"), ("Eli Lilly and Co", 1.41579, "0P000001WJ"),
        ("Berkshire Hathaway Inc Class B", 1.40759, "0P000000RD"), ("JPMorgan Chase & Co", 1.36322, "0P0000031C"),
        ("ExxonMobil Holdings Corp", 0.98712, "0P00000220"), ("Johnson & Johnson", 0.97716, "0P0000032S"),
        ("Visa Inc Class A", 0.93616, "0P0000CPCP"), ("Intel Corp", 0.91374, "0P000002X8"),
        ("Walmart Inc", 0.7195, "0P000005UH"), ("AbbVie Inc", 0.69834, "0P0000XPGW"),
        ("Mastercard Inc Class A", 0.68622, "0P00005U6B"), ("Palantir Technologies Inc", 0.65239, "0P0001KOSE"),
        ("Cisco Systems Inc", 0.62871, "0P0000019Y"), ("Costco Wholesale Corp", 0.61179, "0P000001IK"),
        ("Chevron Corp", 0.60414, "0P00000185"),
    ],
    "CIBR": [
        ("CrowdStrike Holdings Inc Class A", 8.8239, "0P0001HOOZ"), ("Fortinet Inc", 8.11076, "0P0000L1GP"),
        ("Palo Alto Networks Inc", 8.06734, "0P0000WI3J"), ("Cisco Systems Inc", 7.59553, "0P0000019Y"),
        ("Broadcom Inc", 7.42141, "0P0000KU35"), ("Cloudflare Inc", 4.56099, "0P0001ID95"),
        ("Okta Inc Class A", 4.32904, "0P0001A2H3"), ("Zscaler Inc", 3.64145, "0P0001CT73"),
        ("F5 Inc", 3.57543, "0P00000225"), ("Rubrik Inc Class A", 2.68747, "0P0001SOH2"),
        ("Datadog Inc Class A", 2.22819, "0P0001IEZ0"), ("NetApp Inc", 2.1684, "0P000003UY"),
        ("Dynatrace Inc", 2.08261, "0P0001I3W4"), ("Akamai Technologies Inc", 2.07675, "0P0000007V"),
        ("Arista Networks Inc", 2.05835, "0P0001354B"), ("Alphabet Inc Class A", 1.98522, "0P000002HD"),
        ("Microsoft Corp", 1.97309, "0P000003MH"), ("International Business Machines Corp", 1.85463, "0P000002RH"),
        ("Accenture PLC Class A", 1.80725, "0P0000004C"), ("Thales", 1.78376, "0P00009WR9"),
        ("Check Point Software Technologies Ltd", 1.77321, "0P0000017H"), ("JFrog Ltd", 1.74441, "0P0001KOMG"),
        ("Leidos Holdings Inc", 1.71524, "0P00006F08"), ("Infosys Ltd ADR", 1.7146, "0P000002VR"),
        ("Gen Digital Inc", 1.49167, "0P0000058I"),
    ],
    "BKCH": [
        ("Coinbase Global Inc Class A", 13.73261, "0P0001M2C4"), ("Circle Internet Group Inc Class A", 11.06952, "0P0001V0FO"),
        ("BitMine Immersion Technologies Inc", 10.53879, "0P000007QU"), ("IREN Ltd", 10.02159, "0P0001NS43"),
        ("Hut 8 Corp", 4.91436, "0P0001QUQ0"), ("Galaxy Digital Inc Class A", 4.47444, "0P0000KUS8"),
        ("Riot Platforms Inc", 4.34149, "0P000000JX"), ("MARA Holdings Inc", 4.33296, "0P0000STDD"),
        ("Cleanspark Inc", 3.92663, "0P0000SUUT"), ("Applied Digital Corp", 3.62733, "0P0000028I"),
        ("TeraWulf Inc", 3.46771, "0P0001O3VA"), ("Core Scientific Inc", 3.22923, "0P0001SB7W"),
        ("Cipher Digital Inc", 3.03772, "0P0001N7IB"), ("Bullish", 3.02697, "0P0001X1C0"),
        ("Bitdeer Technologies Group Class A", 2.99592, "0P0001QTHE"), ("Keel Infrastructure Corp", 2.6739, None),
        ("Etoro Group Ltd Class A", 2.28376, "0P0001UYVI"), ("Bit Digital Inc", 1.17892, "0P0001CXJT"),
        ("HIVE Digital Technologies Ltd", 1.14444, "0P0000Q3W8"), ("OSL Group Ltd", 1.06292, "0P0000VXNV"),
        ("Canaan Inc ADR", 0.79881, "0P0001IRFS"), ("Chaince Digital Holdings Inc", 0.55201, "0P0001QKN1"),
        ("Gemini Space Station Inc Class A", 0.52093, "0P0001XC85"), ("Bakkt Inc Class A", 0.37539, "0P0001NKNQ"),
        ("Soluna Holdings Inc", 0.36157, "0P000003IV"),
    ],
    "BRIJ": [
        ("Thales", 8.49625, "0P00009WR9"), ("Vinci SA", 7.90171, "0P00009WSC"), ("Aena SME SA", 7.44972, "0P00015CW1"),
        ("Holcim Ltd", 7.36224, "0P0000A5DZ"), ("Ferrovial NV", 7.31566, "0P0000AT1J"), ("Leonardo SpA", 5.40036, "0P00009DKB"),
        ("Orsted AS", 4.61966, "0P0001846T"), ("Verbund AG Class A", 3.95136, "0P0000DLBX"),
        ("Telefonica SA", 3.45264, "0P0000A5SI"), ("Cellnex Telecom SA", 3.11931, "0P00015ZES"),
        ("STRABAG SE", 3.09822, "0P0000DLEB"), ("Acciona SA", 3.06178, "0P0000A5S6"),
        ("Telecom Italia SpA", 2.88635, "0P00009DOA"), ("Skanska AB Class B", 2.55694, "0P0000A6H2"),
        ("Eiffage SA", 2.54689, "0P00009WFJ"), ("Ackermans & Van Haaren NV", 2.20037, "0P0000A5LS"),
        ("Aeroports de Paris SA", 2.18732, "0P00009W9W"), ("Getlink SE", 1.86293, "0P00009WI3"),
        ("Buzzi SpA", 1.71461, "0P00009DIE"), ("NKT AS", 1.62853, "0P0000A5KX"), ("Redeia Corporacion SA", 1.4537, "0P0000A5UI"),
        ("Nexans", 1.44589, "0P00009WMC"), ("Flughafen Zuerich AG", 1.31312, "0P0000A5DR"),
        ("Balfour Beatty PLC", 1.27231, "0P000090TX"), ("BKW AG", 1.19566, "0P0000UURC"),
    ],
    "SOXQ": [
        ("NVIDIA Corp", 11.52754, "0P000003RE"), ("Broadcom Inc", 8.74731, "0P0000KU35"),
        ("Micron Technology Inc", 8.14979, "0P000003MC"), ("Intel Corp", 4.8051, "0P000002X8"),
        ("Advanced Micro Devices Inc", 4.78693, "0P0000006A"), ("Marvell Technology Inc", 4.41163, "0P000003H5"),
        ("Qualcomm Inc", 4.07653, "0P000004J4"), ("Analog Devices Inc", 4.04766, "0P000000FH"),
        ("Taiwan Semiconductor Manufacturing ADR", 4.04212, "0P000005AR"), ("KLA Corp", 3.99677, "0P0000033M"),
        ("Texas Instruments Inc", 3.95397, "0P000005EI"), ("Applied Materials Inc", 3.93605, "0P000000H9"),
        ("ASML Holding NV ADR", 3.87167, "0P0000002X"), ("Lam Research Corp", 3.86648, "0P00000384"),
        ("Monolithic Power Systems Inc", 2.79244, "0P000003OZ"), ("Teradyne Inc", 2.63902, "0P000005DY"),
        ("Astera Labs Inc", 2.56364, "0P0001SG1A"), ("NXP Semiconductors NV", 2.50662, "0P0000PO4S"),
        ("Coherent Corp", 2.3265, "0P000002S3"), ("Microchip Technology Inc", 1.78085, "0P000003M7"),
        ("ARM Holdings PLC ADR", 1.73251, "0P0001RJKB"), ("Credo Technology Group", 1.52309, "0P0001OBCD"),
        ("ON Semiconductor Corp", 1.23883, "0P0000040N"), ("GLOBALFOUNDRIES Inc", 1.10275, "0P0001NLO7"),
        ("Qnity Electronics Inc", 1.09914, "0P0001VS7W"),
    ],
    # DRAM: posições diretas + swaps (mesmo ms_id da ação). T-Bills/money market = colateral.
    "DRAM": [
        ("Samsung Electronics Co Ltd", 18.84069, "0P0000B2XZ"),
        ("Micron Technology Inc (swap)", 16.54331, "0P000003MC"),
        ("SK hynix Inc", 16.52717, "0P0000AZ1B"),
        ("First American Government Obligs X", 15.3101, "CASH"),
        ("United States Treasury Bills", 11.28859, "CASH"),
        ("Micron Technology Inc (swap Goldman)", 9.82879, "0P000003MC"),
        ("Samsung Electronics (swap Goldman)", 5.94203, "0P0000B2XZ"),
        ("SK hynix Inc (swap Goldman)", 5.28265, "0P0000AZ1B"),
        ("CXMT Corporation (swap Goldman)", 5.17616, "CXMT"),
        ("SanDisk Corp", 4.74385, "0P0001U8JM"), ("Seagate Technology Holdings PLC", 4.66192, "0P000004VE"),
        ("United States Treasury Bills", 3.77045, "CASH"), ("United States Treasury Bills", 3.75106, "CASH"),
        ("United States Treasury Bills", 3.73435, "CASH"), ("Western Digital Corp", 3.58813, "0P000005X1"),
        ("Kioxia Holdings Corp", 3.26572, "0P0001KMEE"), ("Nanya Technology Corp", 2.38513, "0P0000AZD9"),
        ("Winbond Electronics Corp", 1.08564, "0P0000BEGR"), ("GigaDevice Semiconductor Inc Class A", 1.02024, "0P00018JMI"),
        ("SK hynix Inc ADR", 0.59852, "0P0000AZ1B"), ("Micron Technology Inc", 0.41672, "0P000003MC"),
        ("Samsung Electronics Pref", 0.11207, "0P0000B2XZ"),
        ("Cash Offset", -37.21177, "CASH"), ("Other assets and liabilities", -0.66643, "CASH"), ("US Dollars", 0.02481, "CASH"),
    ],
    "GRDU": [
        ("Johnson Controls International PLC", 8.59483, "0P0000032T"), ("Eaton Corp PLC", 8.56624, "0P000001UX"),
        ("Quanta Services Inc", 8.4697, "0P000004JC"), ("ABB Ltd", 7.82485, "0P0000A5G8"),
        ("Schneider Electric SE", 7.69849, "0P00009WP6"), ("Prysmian SpA", 3.97975, "0P00009DN8"),
        ("National Grid PLC", 3.75758, "0P000090S9"), ("nVent Electric PLC", 3.47915, "0P0001D4SL"),
        ("Hubbell Inc", 3.00555, "0P000002Q2"), ("Terna SpA", 2.16017, "0P00009DOD"),
        ("NVIDIA Corp", 2.06802, "0P000003RE"), ("Tesla Inc", 1.93807, "0P0000OQN8"),
        ("Cisco Systems Inc", 1.92724, "0P0000019Y"), ("Hydro One Ltd", 1.68056, "0P00016YTR"),
        ("HD Hyundai Electric", 1.53563, "0P0001AFHI"), ("LS Electric Co Ltd", 1.38926, "0P0000AF2O"),
        ("Belimo Holding AG", 1.31577, "0P0000A5FI"), ("Oracle Corp", 1.28621, "0P0000043L"),
        ("SAP SE", 1.2688, "0P00009QRW"), ("Texas Instruments Inc", 1.25532, "0P000005EI"),
        ("Equatorial SA", 1.24051, "0P0000D6L8"), ("GE Vernova Inc", 1.17787, "0P0001RSOL"),
        ("SPIE SA", 1.11944, "0P00014D8D"), ("International Business Machines Corp", 1.02672, "0P000002RH"),
        ("NKT AS", 1.02187, "0P0000A5KX"),
    ],
}

# Nome consolidado para a look-through (classes de ação / ADR / preferencial → mesma empresa)
ISSUER_ALIAS = {"0P00012BBI": "0P000002HD"}  # Alphabet C → Alphabet A
ISSUER_NAME = {
    "0P000002HD": "Alphabet (A+C)", "0P000003MC": "Micron Technology", "0P0000B2XZ": "Samsung Electronics",
    "0P0000AZ1B": "SK hynix", "CXMT": "CXMT (ChangXin Memory, via swap)",
}

# ── Câmbio (unidades de moeda local por 1 USD), 29/09/2026 ──
FX_PER_USD = {"USD": 1.0, "EUR": 1 / 1.1381, "GBP": 0.75644, "CHF": 0.82788, "DKK": 7.4600 / 1.1381,
              "KRW": 1359.64, "JPY": 157.30, "TWD": 31.872, "CNY": 6.7040}

# ── Morningstar Data Tool — nível ação ──
# ticker, país, setor, moeda, mcap (mi, moeda local), preço (moeda local), 1D, YTD, 1A (%),
# P/E TTM, P/E fwd, P/B, ROE (fração), div. yield (fração), P/FV, moat
S = lambda *a: dict(zip(("ticker", "country", "sector", "cur", "mcap", "price", "r1d", "ytd", "r1y",
                         "pe", "fpe", "pb", "roe", "dy", "pfv", "moat"), a))
STOCKS = {
    "0P000003RE": S("NVDA", "EUA", "Tecnologia", "USD", 5526282.42, 228.86, 1.68392, 22.9866, 28.72776, 28.932996, 24.822126, 24.133924, 1.204327, 0.002272, 0.738258, "Wide"),
    "0P000000GY": S("AAPL", "EUA", "Tecnologia", "USD", 4938670.512, 338.4, -0.78283, 24.7701, 32.88186, 38.807339, 35.213319, 45.979104, 1.459263, 0.003132, 1.166897, "Wide"),
    "0P000003MH": S("MSFT", "EUA", "Tecnologia", "USD", 3781236.274927, 509.22, -1.34646, 5.8579, 0.27373, 28.368802, 25.698713, 8.549024, 0.342212, 0.007148, 0.8487, "Wide"),
    "0P000000B7": S("AMZN", "EUA", "Consumo cíclico", "USD", 2655051.085748, 246.15, -1.40986, 6.64154, 11.99836, 19.802896, 23.35389, 4.81171, 0.320874, 0.0, 0.8205, "Wide"),
    "0P000002HD": S("GOOGL", "EUA", "Comunicação", "USD", 4171968.233326, 342.75, -0.3402, 9.71246, 39.37292, 17.197692, 22.292683, 6.734297, 0.538786, 0.002509, 0.79157, "Wide"),
    "0P00012BBI": S("GOOG", "EUA", "Comunicação", "USD", 4171968.233326, 339.16, -0.56292, 8.28872, 37.55967, 17.017561, 22.059187, 6.663761, 0.538786, 0.002536, 0.783279, "Wide"),
    "0P0000KU35": S("AVGO", "EUA", "Tecnologia", "USD", 1668717.791908, 349.57, -0.91834, 1.56602, 5.27307, 44.645012, 18.623868, 16.68279, 0.453568, 0.007438, 0.5378, "Wide"),
    "0P0000W3KZ": S("META", "EUA", "Comunicação", "USD", 1823046.404735, 715.62, -4.79472, 8.65109, -3.49983, 26.963832, 21.20984, 6.98133, 0.306394, 0.002935, 0.841906, "Wide"),
    "0P000003MC": S("MU", "EUA", "Tecnologia", "USD", 1190357.793291, 1053.98, -2.61485, 269.3914, 570.50932, 23.824141, 6.746335, 11.818016, 0.749016, 0.000503, 1.239976, "None"),
    "0P0000OQN8": S("TSLA", "EUA", "Consumo cíclico", "USD", 1411765.715985, 357.45, -3.9397, -20.51721, -18.83515, 330.972222, 149.560669, 16.251469, 0.047077, 0.0, 0.794333, "Narrow"),
    "0P0000006A": S("AMD", "EUA", "Tecnologia", "USD", 992332.603781, 607.87, -3.60909, 183.83919, 281.20532, 155.068878, 39.066195, 14.757287, 0.102637, 0.0, 1.146925, "Narrow"),
    "0P000001WJ": S("LLY", "EUA", "Saúde", "USD", 1056062.023471, 1184.78, 0.11154, 10.72784, 64.44503, 39.771064, 25.101271, 31.176581, 0.999086, 0.005647, 1.208959, "Wide"),
    "0P0001HOOZ": S("CRWD", "EUA", "Tecnologia", "USD", 265455.107789, 259.25, 2.82394, 121.22195, 115.40443, 4713.636364, 207.4, 52.027862, 0.017948, 0.0, 1.705592, "Wide"),
    "0P0000L1GP": S("FTNT", "EUA", "Tecnologia", "USD", 129375.728433, 176.33, 1.65456, 122.05012, 109.12002, 62.30742, 45.563307, 83.28791, 1.612994, 0.0, 1.233077, "Wide"),
    "0P0000WI3J": S("PANW", "EUA", "Tecnologia", "USD", 320729.62, 392.09, 4.62988, 112.86102, 93.74907, 980.225, 93.801435, 11.623503, 0.018941, 0.0, 1.306967, "Wide"),
    "0P0000019Y": S("CSCO", "EUA", "Tecnologia", "USD", 420831.722824, 106.74, 0.03749, 40.19213, 61.26153, 32.054054, 19.877095, 8.376177, 0.275724, 0.015552, 0.928174, "Wide"),
    "0P0001ID95": S("NET", "EUA", "Tecnologia", "USD", 126048.658313, 353.99, 1.42399, 79.55364, 63.6267, None, 179.690355, 77.77436, -0.143394, 0.0, 1.330789, "Wide"),
    "0P0001A2H3": S("OKTA", "EUA", "Tecnologia", "USD", 35345.295223, 202.18, 3.58113, 133.8152, 121.78587, 121.795181, 53.486772, 5.068765, 0.042876, 0.0, 1.0109, "None"),
    "0P0001CT73": S("ZS", "EUA", "Tecnologia", "USD", 32511.476234, 199.39, 3.28412, -11.3507, -32.32988, None, 40.858607, 12.512806, -0.028869, 0.0, 0.79756, "Narrow"),
    "0P00000225": S("FFIV", "EUA", "Tecnologia", "USD", 24664.535392, 435.56, -1.69277, 70.63386, 34.07209, 34.705976, 23.499326, 6.419313, 0.200613, 0.0, 1.0889, "Narrow"),
    "0P0001SOH2": S("RBRK", "EUA", "Tecnologia", "USD", 23444.058328, 113.09, 3.2314, 47.86872, 37.66281, None, 595.210526, None, None, 0.0, None, None),
    "0P000002X8": S("INTC", "EUA", "Tecnologia", "USD", 613346.79355, 116.03, -5.66667, 214.44444, 226.84507, None, 59.963824, 6.684098, -0.10814, 0.0, 1.105048, "None"),
    "0P0001M2C4": S("COIN", "EUA", "Financeiro", "USD", 50601.283462, 191.79, -1.7016, -15.18971, -38.64487, None, 52.617284, 3.867892, -0.071092, 0.0, 1.141607, "None"),
    "0P0001V0FO": S("CRCL", "EUA", "Financeiro", "USD", 21782.55059, 85.8, -3.59551, 8.19672, -32.43562, 58.767123, 69.756098, 6.178116, 0.144084, 0.0, None, None),
    "0P000007QU": S("BMNR", "EUA", "Financeiro", "USD", 16190.596415, 26.84, -2.61248, -1.1418, -46.83168, None, None, 1.341245, -1.057215, 0.000373, None, None),
    "0P0001NS43": S("IREN", "Austrália", "Financeiro", "USD", 16440.126795, 41.72, -5.45042, 10.45804, -0.33445, None, None, 3.789571, -0.249954, 0.0, 0.971163, "None"),
    "0P0001QUQ0": S("HUT", "EUA", "Financeiro", "USD", 11427.385278, 92.71, -4.24499, 101.8067, 179.58384, None, None, 7.916827, -0.490014, 0.0, None, None),
    "0P0000KUS8": S("GLXY", "EUA", "Financeiro", "USD", 4509.526418, 23.21, -4.24917, 3.80143, -24.88673, None, 107.199601, 2.479636, -0.157026, 0.0, None, None),
    "0P000000JX": S("RIOT", "EUA", "Financeiro", "USD", 8113.098175, 21.62, -6.0, 70.63931, 22.21594, None, None, 3.727445, -0.464649, 0.0, None, None),
    "0P0000STDD": S("MARA", "EUA", "Financeiro", "USD", 4678.084487, 12.11, -3.50598, 34.85523, -24.9225, None, None, 2.785007, -0.999284, 0.0, None, None),
    "0P0000SUUT": S("CLSK", "EUA", "Financeiro", "USD", 3425.939754, 13.34, -4.37276, 31.81818, 2.9321, None, None, 4.499866, -0.669525, 0.0, None, None),
    "0P0000028I": S("APLD", "EUA", "Tecnologia", "USD", 7338.644638, 24.53, -6.55238, 0.04078, 12.98941, None, None, 4.111723, -0.145716, 0.0, None, None),
    "0P00009WR9": S("HO FP", "França", "Industriais", "EUR", 46478.636358, 226.0, -1.48213, -0.36989, -11.33822, 31.129477, 17.371253, 5.799272, 0.190643, 0.017257, 0.733766, "Wide"),
    "0P00009WSC": S("DG FP", "França", "Industriais", "EUR", 61394.618265, 111.15, -0.13477, -4.12328, -0.51392, 12.336293, 11.026786, 2.0135, 0.181387, 0.044984, 0.771875, "Narrow"),
    "0P00015CW1": S("AENA SM", "Espanha", "Industriais", "EUR", 38490.0, 25.66, -0.85008, 12.30059, 16.55773, 4.227348, 15.937888, 4.448614, 0.337322, 0.042479, 0.95037, "Wide"),
    "0P0000A5DZ": S("HOLN SW", "Suíça", "Materiais básicos", "CHF", 37424.44501, 67.66, 0.59471, -10.80247, 3.0303, 96.657143, 14.614644, 2.368486, 0.029136, 0.025126, 1.073968, "Narrow"),
    "0P0000AT1J": S("FER SM", "Holanda", "Industriais", "EUR", 40174.318534, 55.77, -0.10747, -12.68093, 0.9044, 30.635651, 43.340068, 6.154204, 0.260639, 0.023071, 0.612967, "Wide"),
    "0P00009DKB": S("LDO IM", "Itália", "Industriais", "EUR", 28392.849652, 49.225, 0.51046, 1.41375, -5.93396, 24.565641, 16.630068, 2.941109, 0.161164, 0.012798, 0.723897, "Narrow"),
    "0P0001846T": S("ORSTED DC", "Dinamarca", "Utilities", "DKK", 177616.7859, 134.45, -1.86131, 9.88966, 16.81147, None, 15.74356, 1.444391, -0.017829, 0.0, 0.840313, "None"),
    "0P0000DLBX": S("VER AV", "Áustria", "Utilities", "EUR", 22460.4241, 64.65, 3.35731, 9.35484, 11.51316, 18.646767, 16.879896, 2.322835, 0.134166, 0.030936, 1.059836, "Wide"),
    "0P0000A5SI": S("TEF SM", "Espanha", "Comunicação", "EUR", 19175.462734, 3.407, -1.1891, 1.83224, -15.09391, None, 12.389091, 1.306676, -0.111609, 0.088054, 0.81119, "None"),
    "0P00015ZES": S("CLNX SM", "Espanha", "Imobiliário", "EUR", 15416.889127, 23.35, -2.66778, -12.14772, -15.97671, None, 122.894737, 1.328233, -0.026915, 0.032029, 0.614474, "Narrow"),
    "0P000003H5": S("MRVL", "EUA", "Tecnologia", "USD", 226383.692015, 251.9, -3.8311, 196.6345, 203.1622, 82.861842, 60.047676, 12.20032, 0.168073, 0.000953, 0.839667, "Narrow"),
    "0P000004J4": S("QCOM", "EUA", "Tecnologia", "USD", 200239.980103, 187.48, -7.17433, 11.2014, 12.94326, 21.699074, 18.562376, 7.164884, 0.366228, 0.019309, 1.102824, "Narrow"),
    "0P000000FH": S("ADI", "EUA", "Tecnologia", "USD", 191611.721825, 395.43, 0.46494, 47.02434, 61.46389, 46.963183, 23.813911, 5.740795, 0.122351, 0.010849, 0.888607, "Wide"),
    "0P000005AR": S("TSM", "Taiwan", "Tecnologia", "USD", 2017084.33551, 452.88, 0.50376, 50.01012, 67.05486, 32.916672, 21.452686, 11.646449, 0.406538, 0.008349, 0.84809, "Wide"),
    "0P0000033M": S("KLAC", "EUA", "Tecnologia", "USD", 246868.078092, 189.17, 0.66518, 56.22017, 78.53217, 51.685792, 34.999075, 38.936847, 0.883993, 0.00444, 1.080971, "Wide"),
    "0P0000B2XZ": S("005930 KS", "Coreia do Sul", "Tecnologia", "KRW", 1734426018.9795, 272500.0, 0.92593, 127.89491, 225.1924, 12.142412, 3.792734, 3.265392, 0.332407, 0.006172, 0.879032, "None"),
    "0P0000AZ1B": S("000660 KS", "Coreia do Sul", "Tecnologia", "KRW", 1255048257.5, 1765000.0, -0.16968, 171.52458, 406.59026, 7.755685, 3.692814, 4.78404, 1.035061, 0.0017, 0.802273, "None"),
    "0P0001U8JM": S("SNDK", "EUA", "Tecnologia", "USD", 250799.642623, 1712.89, -3.65114, 621.58143, 1663.6841, 23.222478, 7.581843, 16.119819, 0.980145, 0.0, 1.71289, "None"),
    "0P000004VE": S("STX", "EUA", "Tecnologia", "USD", 209544.936331, 921.51, 0.51045, 235.42612, 325.35516, 66.292774, 25.776503, 96.531038, 4.967239, 0.003212, 1.316443, "None"),
    "0P000005X1": S("WDC", "EUA", "Tecnologia", "USD", 163407.972049, 453.23, -0.7837, 163.33953, 324.56961, 16.836181, 21.831888, 17.624129, 1.278559, 0.001214, 1.079119, "None"),
    "0P0001KMEE": S("285A JP", "Japão", "Tecnologia", "JPY", 28403817.07338, 17880.0, 0.56243, 414.03929, 1047.37968, 17.618788, 5.646338, 12.157741, None, 0.0, 0.820615, "None"),
    "0P0000AZD9": S("2408 TT", "Taiwan", "Tecnologia", "TWD", 1567905.7174, 506.0, 0.59642, 162.87417, 614.57345, 19.072748, 47.319656, 4.86081, 0.445477, 0.002662, None, None),
    "0P0000BEGR": S("2344 TT", "Taiwan", "Tecnologia", "TWD", 783000.033582, 174.0, 1.45773, 111.25908, 455.73248, 19.226519, None, 4.745178, 0.350553, 0.002874, None, None),
    "0P00018JMI": S("603986 CH", "China", "Tecnologia", "CNY", 253215.308267, 358.51, -6.58207, 67.68261, 88.87545, 31.531223, 41.311387, 6.747889, 0.325353, 0.002092, None, None),
    "0P0000032T": S("JCI", "EUA", "Industriais", "USD", 90188.847468, 148.89, -0.87217, 25.33612, 40.63172, 42.059322, 24.249186, 6.689575, 0.158785, 0.010746, 1.154186, "Narrow"),
    "0P000001UX": S("ETN", "EUA", "Industriais", "USD", 167559.644, 431.41, -1.94782, 36.48237, 19.19416, 43.88708, 27.132704, 8.272916, 0.197989, 0.01006, 1.295526, "Wide"),
    "0P000004JC": S("PWR", "EUA", "Industriais", "USD", 96875.268713, 644.36, -0.73483, 52.74842, 59.03463, 73.809851, 32.758516, 10.046795, 0.153899, 0.000667, 1.57161, "None"),
    "0P0000A5G8": S("ABBN SW", "Suíça", "Industriais", "CHF", 144416.056606, 79.78, -0.49888, 36.3053, 42.31312, 36.555164, 24.324135, 11.274433, 0.334952, 0.011782, 1.190746, "Wide"),
    "0P00009WP6": S("SU FP", "França", "Industriais", "EUR", 163639.001796, 290.5, -0.17182, 25.45764, 25.27099, 34.915865, 23.958763, 6.677683, 0.1985, 0.014458, 1.108779, "Wide"),
    "0P00009DN8": S("PRY IM", "Itália", "Industriais", "EUR", 36676.037033, 122.55, 0.12255, 42.91503, 51.47239, 26.091244, 21.864407, 5.049365, 0.226057, 0.007344, 1.361667, "Narrow"),
    "0P000090S9": S("NG/ LN", "Reino Unido", "Utilities", "GBP", 56677.555391, 11.275, 0.04437, 1.58914, 11.36269, 17.21374, 12.668539, 1.426891, 0.085124, 0.043007, 0.782986, "Narrow"),
    "0P0001D4SL": S("NVT", "Reino Unido", "Industriais", "USD", 25978.19921, 160.5, -2.3782, 58.01706, 66.31959, 44.459834, 24.692308, 6.515889, 0.158349, 0.005171, 1.180147, "Narrow"),
    "0P000002Q2": S("HUBB", "EUA", "Industriais", "USD", 24605.184966, 465.72, -0.19288, 5.82513, 10.86026, 27.573712, 20.730915, 6.290926, 0.242574, 0.012196, 0.927729, "Wide"),
    "0P00009DOD": S("TRN IM", "Itália", "Utilities", "EUR", 18418.370608, 9.18, 0.0654, 4.45107, 12.13349, 18.08949, 17.0, 2.134948, 0.144405, 0.043159, None, None),
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
        mtd = (d["idx_0928"] / d["idx_0831"] - 1) * 100
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
            "since_entry": (d["idx_0928"] / ENTRY[key][1] - 1) * 100 if key in ENTRY else None,
            "cspx_since_entry": (MS_ETF["CSPX"]["idx_0928"] / CSPX_AT_ENTRY[ENTRY[key][0]] - 1) * 100
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


def build_calendar(etfs):
    """Retorno total em USD por ano-calendário (2026 = YTD até REF_DATE) + USD/BRL."""
    by_key = {e["key"]: e for e in etfs}
    rows = []
    for key in ETF_ORDER:
        idx = dict(zip([2021, 2022, 2023, 2024, 2025], YEAR_END_INDEX[key]))
        idx[2026] = MS_ETF[key]["idx_0928"]
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
        "source": "Morningstar MCP (Data Tool, Fund Holdings, X-Ray) · câmbio: fontes públicas 29/09/2026",
        "fx_per_usd": FX_PER_USD,
        "etfs": etfs, "portfolio": port, "calendar": calendar, "xray": XRAY,
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
