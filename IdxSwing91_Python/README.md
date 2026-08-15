# IdxSwing91 (Python)

Port em Python do EA `IdxSwing91.mq5` (../IdxSwing91_MQL): gatilho de cruzamento do
EMA9 sobre o fechamento, confirmado por rompimento (ordem stop) do extremo da barra de
gatilho, SL no extremo oposto + buffer, TP em múltiplo-R, position sizing por risco-%
(ou lote fixo), trailing opcional por ATR. Envia ordens reais via pacote `MetaTrader5`
e permite rodar backtests sucessivos em vários ativos usando o histórico de preços da
própria API do MT5 (não há Strategy Tester acessível a partir de Python).

**Nota de fidelidade:** o `SwingSignal.mqh` original tem o filtro de regime SMA21
comentado/desativado — o EA em produção usa apenas o cruzamento do EMA9. Este port
mantém esse comportamento (não o que `PARAMETROS.md` descreve).

## Setup

Requer Python 3.10+ e o terminal MetaTrader5 instalado e logado (o pacote `MetaTrader5`
só funciona no Windows, conversando com uma instância do terminal aberta localmente).

```bash
pip install -r requirements.txt
pytest tests/          # roda a suíte sem precisar de conexão com o MT5
```

## Estrutura

```
idxswing91/
  account.py            # login opcional no MT5 (config/account.yaml)
  signal.py               # gatilho EMA9 (stateless)
  risk.py               # cálculo de lote (fixo ou risco-%)
  state_machine.py        # IDLE -> PENDING -> IN_POSITION, usado por backtest e live
  broker/
    mt5_live.py            # ordens reais via pacote MetaTrader5
    mt5_backtest.py          # fills/fechamentos simulados contra OHLC histórico
  data/mt5_history.py         # histórico + specs de símbolo via API do MT5
  backtest/                    # engine, métricas e runner em lote (multi-símbolo)
  live/runner.py                 # polling multi-símbolo, um processo só
config/
  default.yaml                  # parâmetros globais (equivalentes aos Inp* do EA)
  symbols.yaml                   # lista de símbolos + overrides por símbolo
  account.example.yaml            # modelo de login MT5 - copie para account.yaml
scripts/
  run_backtest.py                 # CLI de backtest
  run_live.py                      # CLI de execução ao vivo
```

## Mapeamento de parâmetros (MQL5 -> Python)

| Input MQL5 | Campo em `StrategyConfig` / YAML |
|---|---|
| `InpTimeframe` | `timeframe` (string: `"M15"`, `"H1"`, ...) |
| `InpEMAPeriod` | `ema_period` |
| `InpSMAPeriod` | *(não portado - filtro desativado no EA real)* |
| `InpTriggerValidBars` | `trigger_valid_bars` |
| `InpSLBufferPoints` | `sl_buffer_points` |
| `InpTP_RMultiple` | `tp_r_multiple` |
| `InpUseTrailing` / `InpATRPeriod` / `InpATRMultiplier` | `use_trailing` / `atr_period` / `atr_multiplier` |
| `InpUseFixedLot` / `InpFixedLot` / `InpRiskPercent` | `use_fixed_lot` / `fixed_lot` / `risk_percent` |
| `InpMagicNumber` / `InpTradeComment` / `InpSlippagePoints` | `magic_number` / `trade_comment` / `slippage_points` |
| `InpMaxSpreadPoints` | `max_spread_points` |
| `InpUseTradingHoursFilter` / `InpStartHour` / `InpEndHour` | `use_trading_hours_filter` / `start_hour` / `end_hour` |
| `InpLogLevel` | `log_level` |

Configure os defaults globais em `config/default.yaml` e a lista de símbolos + overrides
por instrumento (ex: `sl_buffer_points` varia muito entre um índice e uma ação) em
`config/symbols.yaml`.

## Conta do broker (conexão com o MT5)

Existem duas formas de conectar aos dados/execução do MT5. Nenhuma exige código extra —
os scripts já tentam as duas automaticamente, nessa ordem:

**Opção A — terminal já logado manualmente (mais simples, nenhum arquivo necessário)**
Abra o MetaTrader5 no Windows, faça login na conta normalmente (demo ou real) e deixe o
terminal aberto. Ao rodar `run_backtest.py`/`run_live.py`, o script encontra esse
terminal já conectado (`mt5.terminal_info()`) e usa a conta que já está logada nele. Não
precisa configurar nada em arquivo.

**Opção B — o próprio script faz login (útil para automatizar/trocar de conta sem
abrir a interface manualmente)**
1. Copie `config/account.example.yaml` para `config/account.yaml`.
2. Preencha `login` (número da conta), `password` e `server` (nome exato do servidor,
   igual aparece na tela de login do terminal, ex: `"XPInvestimentos-PRD"`,
   `"MetaQuotes-Demo"`).
3. Só preencha `path` se o MT5 não conseguir se auto-detectar (ex: instalação
   portátil/segunda instância) — normalmente pode deixar comentado.

`config/account.yaml` está no `.gitignore` — nunca é versionado, então a senha não vai
parar no Git. Se esse arquivo existir, os scripts fazem login com essas credenciais
automaticamente (via `mt5.initialize(login=..., password=..., server=...)`); se não
existir, caem para a Opção A.

Para usar uma conta diferente da padrão em uma chamada específica, use
`--account-config caminho/outra_conta.yaml`.

⚠️ Qualquer que seja a opção, o backtest também acessa o histórico pela conta logada —
então a profundidade/qualidade dos dados retornados depende do que o servidor daquele
broker disponibiliza para essa conta (alguns brokers limitam histórico em contas demo).

## Backtest

```bash
python scripts/run_backtest.py --from 2023-01-01 --to 2024-01-01
python scripts/run_backtest.py --symbols US500,PETR4 --from 2023-06-01 --to 2023-12-31
```

Gera `backtest_results/summary.csv` (métricas por símbolo) e um
`backtest_results/<symbol>_trades.csv` por símbolo.

**Limitações conhecidas do backtest** (por rodar só com OHLC, sem tick-by-tick):
- Preenchimento de ordem stop, SL e TP são simulados por barra: se o nível de entrada e
  o SL forem tocados na mesma barra, assume-se o pior caso (SL primeiro). Isso pode ser
  pessimista, mas evita otimismo irreal.
- Entradas e saídas são simuladas sem slippage, no preço exato do nível — o PnL do
  backtest tende a ser um limite superior otimista frente à execução real.
- O filtro de spread usa o campo `spread` retornado pelo histórico do MT5 (spread por
  barra), não o spread tick-a-tick real.

## Execução ao vivo

```bash
python scripts/run_live.py --poll-interval 5 --log-file logs/idxswing91.log
```

Um único processo monitora todos os símbolos de `config/symbols.yaml`, mantendo o
estado (IDLE/PENDING/IN_POSITION) por símbolo e enviando ordens reais via
`MetaTrader5.order_send`. **Valide primeiro em conta demo.**
