# IdxSwing91 — Referência de Parâmetros de Entrada

Este documento explica cada parâmetro editável (`input`) do EA `IdxSwing91.mq5`, agrupado na mesma ordem em que aparecem no código. Use como referência ao configurar o EA no gráfico ou ao montar um `.set` para o Strategy Tester.

## Timeframe

| Parâmetro | Tipo | Padrão |
|---|---|---|
| `InpTimeframe` | `ENUM_TIMEFRAMES` | `PERIOD_CURRENT` |

Define em qual timeframe o EA calcula EMA(9), SMA(21) e detecta barras novas — **não precisa ser o mesmo timeframe do gráfico visível**. Com `PERIOD_CURRENT`, o EA usa o período do próprio gráfico onde está anexado. Se você quiser, por exemplo, ver a execução em modo visual num gráfico M15 mas operar a estratégia em H4, basta selecionar `PERIOD_H4` aqui — o EA ignora o período do gráfico e passa a trabalhar só com barras H4.

## Estratégia (EMA9 / SMA21 / RSI)

| Parâmetro | Tipo | Padrão | O que faz |
|---|---|---|---|
| `InpEMAPeriod` | `int` | `9` | Período da média móvel exponencial usada como gatilho de entrada (cruzamento). |
| `InpSMAPeriod` | `int` | `21` | Período da média móvel simples originalmente pensada como filtro de regime. **Atualmente sem efeito** — o filtro está comentado no código (`SwingSignal.mqh`), mantido só para religar facilmente no futuro. |
| `InpTriggerValidBars` | `int` | `3` | Quantas barras a ordem pendente (Buy Stop/Sell Stop) fica ativa depois que o gatilho dispara. Se o preço não romper o nível da barra de gatilho dentro desse prazo, a ordem é cancelada automaticamente. |
| `InpRSIPeriod` | `int` | `3` | Período do RSI usado para confirmar o gatilho de cruzamento da EMA. |
| `InpRSIBuyLevel` | `double` | `70.0` | Nível mínimo de RSI (na barra de gatilho) para confirmar um sinal de **compra**. Precisa ser maior que `InpRSISellLevel`. |
| `InpRSISellLevel` | `double` | `30.0` | Nível máximo de RSI (na barra de gatilho) para confirmar um sinal de **venda**. Precisa ser menor que `InpRSIBuyLevel`. |

Lógica atual do gatilho: a cada barra fechada, o EA compara o fechamento da barra atual e da anterior contra a EMA(`InpEMAPeriod`) calculada em cada uma delas. Um cruzamento para cima (`crossedUp`) só vira sinal de **compra** se o RSI da barra de gatilho estiver **acima** de `InpRSIBuyLevel`; um cruzamento para baixo (`crossedDown`) só vira sinal de **venda** se o RSI estiver **abaixo** de `InpRSISellLevel`. Ou seja, o RSI funciona como confirmação de momentum — não basta cruzar a EMA, o RSI precisa já estar esticado na direção do sinal. Com os padrões (`RSI(3)`, 70/30), isso torna o filtro relativamente exigente: espere menos sinais do que só com o cruzamento da EMA. O filtro de SMA21 mencionado no cabeçalho da seção está desligado no código atual (ver nota acima) — o gatilho de hoje é EMA + RSI, não EMA + SMA. Aumentar `InpTriggerValidBars` deixa o sistema mais tolerante a atrasos no rompimento; diminuir deixa mais seletivo (só entra se o rompimento for quase imediato).

## Stop Loss / Take Profit

| Parâmetro | Tipo | Padrão | O que faz |
|---|---|---|---|
| `InpSLBufferPoints` | `int` | `30` | Pontos adicionados além da extremidade oposta da barra de gatilho ao calcular o Stop Loss (mínima da barra, menos o buffer, para compra; máxima, mais o buffer, para venda). Existe para evitar que o preço toque o SL exatamente no nível técnico por uma variação mínima. |
| `InpTP_RMultiple` | `double` | `2.0` | Múltiplo da distância do Stop Loss usado para calcular o Take Profit (ex: `2.0` = TP a 2x a distância do SL, um "2R"). |

**Ponto de atenção:** `InpSLBufferPoints` é em **pontos** do símbolo (não pips nem "ticks"), e o valor de um ponto varia muito entre índices e ações — vale conferir a especificação do símbolo (`SYMBOL_POINT`) antes de assumir que 30 pontos é uma distância razoável num índice específico.

## Trailing Stop (ATR)

| Parâmetro | Tipo | Padrão | O que faz |
|---|---|---|---|
| `InpUseTrailing` | `bool` | `false` | Liga/desliga o trailing stop. Desligado por padrão de propósito — a ideia é avaliar primeiro o comportamento do sistema-base (SL fixo + TP em R) antes de somar outra variável. |
| `InpATRPeriod` | `int` | `14` | Período do ATR usado para calcular a distância do trailing. |
| `InpATRMultiplier` | `double` | `2.0` | Multiplicador do ATR: o SL passa a seguir o preço a uma distância de `ATR × este valor`. |

O trailing só é reavaliado a cada barra nova fechada (não a cada tick) e **só aperta o stop, nunca afrouxa** — se o novo nível calculado for pior que o SL atual, ele é ignorado.

## Dimensionamento de posição (lote)

| Parâmetro | Tipo | Padrão | O que faz |
|---|---|---|---|
| `InpUseFixedLot` | `bool` | `false` | Se `true`, ignora o cálculo por risco e usa sempre `InpFixedLot`. |
| `InpFixedLot` | `double` | `0.10` | Lote fixo usado quando `InpUseFixedLot = true`. |
| `InpRiskPercent` | `double` | `1.0` | % do saldo da conta arriscado por operação (modo recomendado, usado quando `InpUseFixedLot = false`). |

No modo por risco-%, o lote é calculado a partir da distância até o SL e do valor por tick do símbolo (`SYMBOL_TRADE_TICK_VALUE`/`SYMBOL_TRADE_TICK_SIZE`) — por isso funciona igual para um índice ou uma ação, sem precisar de tabela de conversão manual por instrumento. O resultado é sempre arredondado para o step de volume permitido pela corretora.

## Gestão de ordens

| Parâmetro | Tipo | Padrão | O que faz |
|---|---|---|---|
| `InpMagicNumber` | `long` | `910091` | Identificador único das ordens/posições deste EA — usado para o EA reconhecer "isto é meu" e não mexer em posições manuais ou de outros EAs no mesmo símbolo. |
| `InpTradeComment` | `string` | `"IdxSwing91"` | Texto anexado a cada ordem enviada (aparece no histórico/terminal). Mantenha curto — algumas corretoras truncam comentários longos. |
| `InpSlippagePoints` | `int` | `10` | Desvio máximo de preço tolerado (em pontos) ao executar ordens — se o preço se mover mais que isso entre o envio e a execução, a ordem é rejeitada em vez de executar a um preço muito pior que o esperado. |

## Filtros opcionais (desligados por padrão)

| Parâmetro | Tipo | Padrão | O que faz |
|---|---|---|---|
| `InpMaxSpreadPoints` | `int` | `0` | Se maior que 0, bloqueia novas entradas quando o spread atual (em pontos) ultrapassar esse valor. `0` = filtro desligado. |
| `InpUseTradingHoursFilter` | `bool` | `false` | Liga/desliga um filtro simples de horário para novas entradas. |
| `InpStartHour` | `int` | `0` | Hora de início da janela permitida (horário do servidor/corretora), usada só se o filtro acima estiver ligado. |
| `InpEndHour` | `int` | `23` | Hora de fim da janela permitida. Se `InpStartHour > InpEndHour`, a janela é interpretada como "atravessando a meia-noite" (ex: 22 a 6). |

Este filtro é deliberadamente simples (uma janela de hora só, sem calendário por instrumento) — não há uma tabela de pregão por índice (NYSE, Xetra, JPX etc.), então para instrumentos com horários de negociação muito diferentes pode valer a pena ajustar `InpStartHour`/`InpEndHour` por símbolo antes de rodar.

## Diagnóstico

| Parâmetro | Tipo | Padrão | O que faz |
|---|---|---|---|
| `InpLogLevel` | `ENUM_LOG_LEVEL` | `LOG_INFO` | Nível mínimo de mensagens que aparecem na aba "Experts"/Journal do MT5: `LOG_DEBUG` (tudo), `LOG_INFO` (eventos normais: ordem colocada, cancelada, etc.), `LOG_WARN` (situações incomuns, ex: gatilho anulado por gap), `LOG_ERROR` (falhas de execução). Use `LOG_DEBUG` ao validar o EA pela primeira vez; volte para `LOG_INFO` ou mais alto em produção para reduzir ruído no log. |

## Símbolo e instrumento

Não existe um parâmetro de símbolo — o EA sempre opera no `_Symbol` do gráfico onde está anexado (uma instância por gráfico/instrumento, conforme decidido no planejamento). Para rodar em vários dos ~13 instrumentos-alvo, anexe uma instância separada em cada gráfico.
