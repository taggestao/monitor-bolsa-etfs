# Atualização diária dos dados (Morningstar MCP)

O app no Streamlit Cloud lê `tag_equities.json`. Ele não acessa o Morningstar sozinho: o
Morningstar MCP é um conector autenticado da conta TAG no claude.ai. Por isso, uma rotina
diária do Claude (com o conector Morningstar) coleta os dados, regenera o JSON e faz push na
`main`. O Streamlit Cloud reimplanta a cada push, então quem abre o app vê o último
fechamento disponível no Morningstar.

## Passo a passo (é o que a rotina executa)

1. `python refresh_morningstar.py --plan` (fase 1) lista as chamadas, cada uma com a ferramenta MCP:
   - `etf_snapshot.json`: snapshot dos 7 ETFs (preço, AUM, retornos, vol, valuation);
   - `etf_index.json`: Daily Return Index (HS793) dos 7 ETFs, do último fim de mês guardado até hoje;
   - `etf_monthly.json`: retorno mensal (HP010) de 6 ETFs (o CSPX não tem HP010; o retorno mensal
     dele sai do HS793);
   - `dram_index.json`: HS793 do DRAM desde o último dia salvo (série desde o lançamento);
   - `holdings.json` (Fund Holdings Tool, top 25 de cada ETF): só quando as holdings gravadas têm
     mais de 7 dias;
   - `xray_equity_statistics.json` e `xray_equity_sectors.json` (Portfolio Analysis Tool, carteira
     TAG pelos pesos atuais): só quando fecha um mês que o X-Ray gravado ainda não tem.
2. Fazer cada chamada e salvar a resposta em `raw/<file>` (fora do repositório). Vale a
   resposta original ou o formato compacto `{"<ms_id>": {"<datapoint>": valor}}` e, para séries,
   `{"<ms_id>": {"HS793": {"AAAA-MM-DD": valor}}}`. Holdings: original ou
   `{"_as_of": "AAAA-MM-DD", "<etf_id>": [["<ms_id>", "<nome>", peso], ...]}` (ms_id vazio quando o
   Morningstar não informa). X-Ray: resposta original. Datapoints ausentes mantêm o valor anterior.
   Depois, `python refresh_morningstar.py --plan-stocks raw/` (fase 2) lista as chamadas das ações
   que o app mostra (top 10 de cada ETF e top 25 da look-through, pelas holdings novas se vieram):
   o snapshot diário, o retorno mensal (HP010) quando fecha um mês e, para ações que entraram
   agora, o cadastro (ticker, país, setor, moeda) e o histórico de retorno mensal desde dez/2024.
   Salvar em `raw/` também.
3. `python refresh_morningstar.py raw/` atualiza `morningstar_data.json`. A data de referência
   é o último dia útil com HS793 do CSPX. O script para com erro se faltar ETF, se a série não
   cobrir o fim do mês anterior ou se o histórico do DRAM tiver lacunas.
   - Também grava o retorno do mês que acabou de fechar em `monthly_returns`, que é a base do
     seletor de data final do app.
   - Busca o câmbio na data de referência: PTAX e EUR, GBP, CHF, DKK e JPY no Banco Central
     (olinda.bcb.gov.br); KRW, TWD e CNY, que o BCB não publica, na currency-api (cdn.jsdelivr.net,
     com espelho em currency-api.pages.dev). Se uma fonte falhar, mantém os valores anteriores.
     Para sobrepor: `--ptax 5.1234 --ptax-date AAAA-MM-DD` ou `--fx KRW=1360 ...`. Para não
     consultar a internet: `--no-bcb`.
4. `python build_tag_equities.py` regenera `tag_equities.json`.
5. Commit de `morningstar_data.json` e `tag_equities.json`, depois push na `main`.

Se a data de referência não mudou (fim de semana ou feriado nos EUA), não há o que commitar.

## Seletor de data final no app

Na barra lateral, "Data final" lista os fechamentos mensais (padrão: o mais recente) e o último
pregão coletado. Num fechamento mensal, o app recalcula todos os retornos até aquele fim de mês:
mês, 3M, YTD, 12M, 24M e 36M, vol 12M, desde a entrada, ano-calendário e carteira. A base são os
retornos mensais do Morningstar em `morningstar_data.json`. Preço, AUM, valuation e a aba de ações
mostram sempre o último pregão coletado. A PTAX da data escolhida é buscada no Banco Central
quando o app abre.

## Pesos digitados e data final na aba Carteira TAG

Na aba **Carteira TAG (look-through)** há um seletor de data final, sincronizado com o da barra
lateral, e um campo de % para cada ETF. Os pesos digitados recalculam a carteira em todas as abas:
retornos, múltiplos, desde a entrada, ano-calendário, look-through e top 10. Se a soma não der
100%, eles são reescalados. Valem só para a sessão de quem digitou; o botão "Restaurar pesos
oficiais" volta para `PORTFOLIO` (`carteira.py`). Num fechamento mensal, a look-through e o top 10
usam:
- o retorno de cada ação no mês, YTD e 12M naquela data (`stock_monthly_returns`, desde dez/2024);
- a fotografia de holdings mais próxima da data (`holdings_history`; a mais antiga é de 28/09/2026,
  porque o Morningstar só entrega holdings atuais);
- market cap e valuation do último pregão.

O X-Ray é sempre o mais recente, com os pesos oficiais.

## Holdings: regras de tratamento (carteira.py)

- Swaps do DRAM vêm sem Morningstar ID e são atribuídos à ação subjacente (Micron, Samsung,
  SK hynix, CXMT) como exposição econômica.
- Fundos monetários (ID começando com F), T-Bills e títulos (B) e saldos em moeda contam como caixa.
- ADR e preferencial são somados à ação principal na look-through e no top 10 do DRAM
  (`ISSUER_ALIAS`).
- Ação nova no top 10 de um ETF ou no top 25 da look-through ganha cadastro automático. Ticker no
  padrão Bloomberg, com sufixo de bolsa; país em português pelo Business Country; setor
  Morningstar.

## Ajustes manuais

Alocação (`PORTFOLIO`) e regras de holdings ficam em `carteira.py`. Descritivos (`ETF_INFO`) e
datas de entrada (`ENTRY`) ficam em `build_tag_equities.py`.
