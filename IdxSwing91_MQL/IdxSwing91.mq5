//+------------------------------------------------------------------+
//|                                                 IdxSwing91.mq5   |
//|   Swing/reversal EA: EMA9 regime trigger + SMA21 filter,         |
//|   confirmed by a breakout of the trigger bar's extreme.         |
//|   One symbol per instance - attach one chart per instrument.    |
//+------------------------------------------------------------------+
#property copyright "IdxSwing91"
#property version   "1.00"
#property strict

// Quoted, path-relative to this .mq5's own folder - resolves correctly
// regardless of where/how this project folder is exposed inside the MT5
// data folder (junction, direct copy, etc.), unlike <angle-bracket>
// includes which only resolve under MQL5\Include\.
#include "Include\IdxSwing91\Defines.mqh"
#include "Include\IdxSwing91\Core\Logger.mqh"
#include "Include\IdxSwing91\Core\BarManager.mqh"
#include "Include\IdxSwing91\Core\RiskManager.mqh"
#include "Include\IdxSwing91\Core\TradeManager.mqh"
#include "Include\IdxSwing91\Signal\SwingSignal.mqh"

//--- Timeframe
input ENUM_TIMEFRAMES InpTimeframe        = PERIOD_CURRENT;

//--- Strategy
input int              InpEMAPeriod        = 9;
input int              InpSMAPeriod        = 21;
input int              InpTriggerValidBars = 3;

//--- Stop Loss / Take Profit
input int              InpSLBufferPoints   = 30;
input double           InpTP_RMultiple     = 2.0;

//--- Trailing (ATR)
input bool              InpUseTrailing      = false;
input int               InpATRPeriod        = 14;
input double            InpATRMultiplier    = 2.0;

//--- Position sizing
input bool              InpUseFixedLot      = false;
input double            InpFixedLot         = 0.10;
input double            InpRiskPercent      = 1.0;

//--- Trade management
input long               InpMagicNumber      = 910091;
input string             InpTradeComment     = "IdxSwing91";
input int                InpSlippagePoints   = 10;

//--- Optional filters (off by default)
input int                InpMaxSpreadPoints       = 0;     // 0 = disabled
input bool                InpUseTradingHoursFilter = false;
input int                 InpStartHour             = 0;    // server/broker time
input int                 InpEndHour               = 23;   // server/broker time

//--- Diagnostics
input ENUM_LOG_LEVEL      InpLogLevel = LOG_INFO;

//--- Globals
CLogger        g_logger;
CBarManager    g_bar;
CRiskManager   g_risk;
CTradeManager  g_trade;
CSwingSignal   g_signal;

ENUM_TIMEFRAMES g_workTF;
int             hATR = INVALID_HANDLE;

ENUM_EA_STATE g_state          = STATE_IDLE;
ulong         g_pendingTicket  = 0;
int           g_barsSincePlaced = 0;

//+------------------------------------------------------------------+
bool ValidateInputs(void)
  {
   if(InpEMAPeriod <= 0 || InpSMAPeriod <= 0)
     {
      g_logger.Log(LOG_ERROR, "ValidateInputs: EMA/SMA period must be > 0");
      return false;
     }
   if(InpTriggerValidBars <= 0)
     {
      g_logger.Log(LOG_ERROR, "ValidateInputs: InpTriggerValidBars must be > 0");
      return false;
     }
   if(InpTP_RMultiple <= 0.0)
     {
      g_logger.Log(LOG_ERROR, "ValidateInputs: InpTP_RMultiple must be > 0");
      return false;
     }
   if(!InpUseFixedLot && (InpRiskPercent <= 0.0 || InpRiskPercent > 20.0))
     {
      g_logger.Log(LOG_ERROR, "ValidateInputs: InpRiskPercent must be in (0, 20]");
      return false;
     }
   if(InpUseFixedLot && InpFixedLot <= 0.0)
     {
      g_logger.Log(LOG_ERROR, "ValidateInputs: InpFixedLot must be > 0");
      return false;
     }
   if(InpUseTrailing && (InpATRPeriod <= 0 || InpATRMultiplier <= 0.0))
     {
      g_logger.Log(LOG_ERROR, "ValidateInputs: ATR period/multiplier must be > 0 when trailing is enabled");
      return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
int OnInit(void)
  {
   g_logger.Init(InpLogLevel);

   if(!ValidateInputs())
      return INIT_PARAMETERS_INCORRECT;

   g_workTF = (InpTimeframe == PERIOD_CURRENT) ? _Period : InpTimeframe;

   if(!g_signal.Init(_Symbol, g_workTF, InpEMAPeriod, InpSMAPeriod, GetPointer(g_logger)))
      return INIT_FAILED;

   if(InpUseTrailing)
     {
      hATR = iATR(_Symbol, g_workTF, InpATRPeriod);
      if(hATR == INVALID_HANDLE)
        {
         g_logger.Log(LOG_ERROR, "OnInit: failed to create ATR handle");
         return INIT_FAILED;
        }
     }

   g_trade.Init(_Symbol, InpMagicNumber, InpSlippagePoints, GetPointer(g_logger));
   g_risk.Init(_Symbol, InpUseFixedLot, InpFixedLot, InpRiskPercent, GetPointer(g_logger));

   g_bar.Reset();
   g_state           = STATE_IDLE;
   g_pendingTicket   = 0;
   g_barsSincePlaced = 0;

   g_logger.Log(LOG_INFO, StringFormat("OnInit: ready. TF=%s EMA=%d SMA=%d TriggerValidBars=%d",
                                        EnumToString(g_workTF), InpEMAPeriod, InpSMAPeriod, InpTriggerValidBars));
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   g_signal.Deinit();
   if(hATR != INVALID_HANDLE)
      IndicatorRelease(hATR);
  }

//+------------------------------------------------------------------+
bool WithinTradingHours(void)
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(InpStartHour <= InpEndHour)
      return dt.hour >= InpStartHour && dt.hour <= InpEndHour;
   // wraps past midnight (e.g. Start=22, End=6)
   return dt.hour >= InpStartHour || dt.hour <= InpEndHour;
  }

//+------------------------------------------------------------------+
int CurrentSpreadPoints(void)
  {
   const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0.0)
      return 0;
   return (int)MathRound((ask - bid) / point);
  }

//+------------------------------------------------------------------+
void RefreshState(void)
  {
   if(g_trade.HasOpenPosition())
     {
      g_state = STATE_IN_POSITION;
      return;
     }

   const ulong pending = g_trade.FindPendingOrder();
   if(pending != 0)
     {
      if(g_state != STATE_PENDING || g_pendingTicket != pending)
        {
         // pending order exists but we didn't place it this run (e.g. EA reload) -
         // adopt it rather than leaving it untracked and un-expirable.
         g_pendingTicket   = pending;
         g_barsSincePlaced = 1;
        }
      g_state = STATE_PENDING;
      return;
     }

   if(g_state == STATE_PENDING && g_pendingTicket != 0)
      g_logger.Log(LOG_INFO, "RefreshState: previously tracked pending order is gone (filled or removed)");

   g_state           = STATE_IDLE;
   g_pendingTicket   = 0;
   g_barsSincePlaced = 0;
  }

//+------------------------------------------------------------------+
void HandleIdleState(void)
  {
   if(InpUseTradingHoursFilter && !WithinTradingHours())
      return;

   ENUM_TRIGGER_DIR dir;
   double levelPrice, oppositeExtreme;
   datetime triggerBarTime;

   if(!g_signal.CheckForTrigger(dir, levelPrice, oppositeExtreme, triggerBarTime))
      return;

   const double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   const double buffer = InpSLBufferPoints * point;

   double entryPrice = levelPrice;
   double slPrice;

   if(dir == TRIGGER_BUY)
      slPrice = oppositeExtreme - buffer;
   else
      slPrice = oppositeExtreme + buffer;

   //--- gap-through guard: void the trigger if price already traded past the level
   const double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   const double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(dir == TRIGGER_BUY && currentAsk >= entryPrice)
     {
      g_logger.Log(LOG_WARN, "HandleIdleState: BUY trigger voided, price already gapped through level");
      return;
     }
   if(dir == TRIGGER_SELL && currentBid <= entryPrice)
     {
      g_logger.Log(LOG_WARN, "HandleIdleState: SELL trigger voided, price already gapped through level");
      return;
     }

   if(InpMaxSpreadPoints > 0 && CurrentSpreadPoints() > InpMaxSpreadPoints)
     {
      g_logger.Log(LOG_INFO, "HandleIdleState: trigger skipped, spread filter");
      return;
     }

   const double riskDistance = MathAbs(entryPrice - slPrice);
   const double tpPrice = (dir == TRIGGER_BUY)
                           ? entryPrice + InpTP_RMultiple * riskDistance
                           : entryPrice - InpTP_RMultiple * riskDistance;

   const double lots = g_risk.CalculateLotSize(riskDistance);

   const ulong ticket = g_trade.PlaceStopOrder(dir, entryPrice, slPrice, tpPrice, lots, InpTradeComment);
   if(ticket > 0)
     {
      g_state           = STATE_PENDING;
      g_pendingTicket   = ticket;
      g_barsSincePlaced = 1;
      g_logger.Log(LOG_INFO, StringFormat("HandleIdleState: placed %s stop @ %.5f SL=%.5f TP=%.5f lots=%.2f ticket=%I64u",
                                           (dir == TRIGGER_BUY ? "BUY" : "SELL"), entryPrice, slPrice, tpPrice, lots, ticket));
     }
   else
      g_logger.Log(LOG_ERROR, "HandleIdleState: order placement failed - " + g_trade.LastError());
  }

//+------------------------------------------------------------------+
void HandlePendingState(void)
  {
   g_barsSincePlaced++;
   if(g_barsSincePlaced > InpTriggerValidBars)
     {
      g_trade.CancelOrder(g_pendingTicket);
      g_logger.Log(LOG_INFO, "HandlePendingState: trigger expired, cancelling pending order");
      g_state           = STATE_IDLE;
      g_pendingTicket   = 0;
      g_barsSincePlaced = 0;
     }
  }

//+------------------------------------------------------------------+
void HandleInPositionState(void)
  {
   if(!InpUseTrailing || hATR == INVALID_HANDLE)
      return;

   double atrBuf[];
   if(CopyBuffer(hATR, 0, 1, 1, atrBuf) != 1)
      return;

   g_trade.ApplyTrailing(atrBuf[0], InpATRMultiplier);
  }

//+------------------------------------------------------------------+
void HandleNewBar(void)
  {
   RefreshState();

   switch(g_state)
     {
      case STATE_IN_POSITION:
         HandleInPositionState();
         break;
      case STATE_PENDING:
         HandlePendingState();
         break;
      case STATE_IDLE:
         HandleIdleState();
         break;
     }
  }

//+------------------------------------------------------------------+
void OnTick(void)
  {
   if(!g_bar.IsNewBar(_Symbol, g_workTF))
      return;

   HandleNewBar();
  }
//+------------------------------------------------------------------+
