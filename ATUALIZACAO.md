# Atualização diária dos dados (Morningstar MCP)

O app no Streamlit Cloud lê `tag_equities.json`. Ele não acessa o Morningstar sozinho: o
Morningstar MCP é um conector autenticado da conta TAG no claude.ai. Por isso, uma rotina
diária do Claude (com o conector Morningstar) coleta os dados, regenera o JSON e faz push na
`main`. O Streamlit Cloud reimplanta a cada push, então quem abre o app vê o último
fechamento disponível no Morningstar.

## Passo a passo (é o que a rotina executa)

1. `python refresh_morningstar.py --plan` lista as chamadas ao `morningstar-data-tool`:
   - `etf_snapshot.json`: snapshot dos 7 ETFs (preço, AUM, retornos, vol, valuation);
   - `etf_index.json`: Daily Return Index (HS793) dos 7 ETFs, do último fim de mês até hoje;
   - `dram_index.json`: HS793 do DRAM desde o último dia salvo (série desde o lançamento);
   - `stocks_NN.json`: ações das holdings, 10 por chamada (no máximo ~10 chamadas por segundo,
     porque o MCP limita a 15 requisições por segundo).
2. Fazer cada chamada e salvar a resposta em `raw/<file>` (fora do repositório). Vale a
   resposta original (`{"result": ...}`) ou o formato compacto
   `{"<ms_id>": {"<datapoint>": valor}}` e, para séries, `{"<ms_id>": {"HS793": {"AAAA-MM-DD": valor}}}`.
   Datapoints ausentes na resposta mantêm o valor anterior.
3. `python refresh_morningstar.py raw/` atualiza `morningstar_data.json`. A data de referência
   é o último dia útil com HS793 do CSPX. O script para com erro se faltar ETF, se a série não
   cobrir o fim do mês anterior ou se o histórico do DRAM tiver lacunas.
   - Opcional: `--ptax 5.1234 --ptax-date AAAA-MM-DD` (PTAX venda do BCB) e
     `--fx EUR=0.86 GBP=0.75 ... --fx-date AAAA-MM-DD` (moeda local por 1 USD).
4. `python build_tag_equities.py` regenera `tag_equities.json`.
5. Commit de `morningstar_data.json` e `tag_equities.json`, depois push na `main`.

Se a data de referência não mudou (fim de semana ou feriado nos EUA), não há o que commitar.

## Atualização manual (mensal)

Holdings (`holdings`, top 25 por ETF, Fund Holdings Tool) e X-Ray da carteira (`xray`,
Portfolio Analysis Tool) mudam pouco e são editados direto em `morningstar_data.json`.
Ações novas nas holdings precisam de uma entrada em `stocks` (ticker, país, setor, moeda); a
partir daí a rotina diária passa a atualizá-las. Alocação (`PORTFOLIO`), descritivos
(`ETF_INFO`) e datas de entrada (`ENTRY`) ficam em `build_tag_equities.py`.
