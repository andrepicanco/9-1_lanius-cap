//+------------------------------------------------------------------+
//|                                                TradeManager.mqh  |
//|      IdxSwing91 - CTrade wrapper: pending orders, trailing       |
//+------------------------------------------------------------------+
#property strict

#include <Trade\Trade.mqh>
#include "..\Defines.mqh"
#include "Logger.mqh"

class CTradeManager
  {
private:
   CTrade            m_trade;
   string            m_symbol;
   long              m_magic;
   int               m_slippagePoints;
   CLogger          *m_logger;

   double            RoundToTickSize(const double price) const
     {
      const double tickSize = SymbolInfoDouble(m_symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tickSize <= 0.0)
         return NormalizeDouble(price, (int)SymbolInfoInteger(m_symbol, SYMBOL_DIGITS));
      return MathRound(price / tickSize) * tickSize;
     }

   int               StopsLevelPoints(void) const
     {
      const int stopsLevel  = (int)SymbolInfoInteger(m_symbol, SYMBOL_TRADE_STOPS_LEVEL);
      const int freezeLevel = (int)SymbolInfoInteger(m_symbol, SYMBOL_TRADE_FREEZE_LEVEL);
      return MathMax(stopsLevel, freezeLevel);
     }

public:
                     CTradeManager(void) : m_symbol(_Symbol), m_magic(0), m_slippagePoints(10), m_logger(NULL) {}

   void              Init(const string symbol, const long magic, const int slippagePoints, CLogger *logger)
     {
      m_symbol         = symbol;
      m_magic          = magic;
      m_slippagePoints = slippagePoints;
      m_logger         = logger;

      m_trade.SetExpertMagicNumber(magic);
      m_trade.SetDeviationInPoints(slippagePoints);
      m_trade.SetTypeFillingBySymbol(symbol);
     }

   //--- returns ticket > 0 on success, 0 on failure
   ulong             PlaceStopOrder(const ENUM_TRIGGER_DIR dir, double entry, double sl, double tp,
                                     const double lots, const string comment)
     {
      const double point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
      const int    minStopPts = StopsLevelPoints();

      entry = RoundToTickSize(entry);
      sl    = RoundToTickSize(sl);
      tp    = RoundToTickSize(tp);

      if(minStopPts > 0)
        {
         const double minDist = (minStopPts + 1) * point;
         if(MathAbs(entry - sl) < minDist)
           {
            if(m_logger != NULL)
               m_logger.Log(LOG_WARN, StringFormat("PlaceStopOrder: SL distance %.5f below broker min %.5f, skipping",
                                                    MathAbs(entry - sl), minDist));
            return 0;
           }
         if(tp > 0.0 && MathAbs(tp - entry) < minDist)
           {
            if(m_logger != NULL)
               m_logger.Log(LOG_WARN, "PlaceStopOrder: TP distance below broker min, skipping");
            return 0;
           }
        }

      bool ok = false;
      if(dir == TRIGGER_BUY)
         ok = m_trade.BuyStop(lots, entry, m_symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
      else
         if(dir == TRIGGER_SELL)
            ok = m_trade.SellStop(lots, entry, m_symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
         else
            return 0;

      if(!ok)
        {
         if(m_logger != NULL)
            m_logger.Log(LOG_ERROR, StringFormat("PlaceStopOrder failed: retcode=%d desc=%s",
                                                  m_trade.ResultRetcode(), m_trade.ResultRetcodeDescription()));
         return 0;
        }

      return m_trade.ResultOrder();
     }

   bool              CancelOrder(const ulong ticket)
     {
      if(ticket == 0)
         return true;
      if(!OrderSelect(ticket))
         return true; // already gone (filled or cancelled elsewhere)
      return m_trade.OrderDelete(ticket);
     }

   //--- true if a position with our magic is open on our symbol
   bool              HasOpenPosition(void) const
     {
      return PositionSelect(m_symbol) && (long)PositionGetInteger(POSITION_MAGIC) == m_magic;
     }

   //--- finds a pending order with our magic on our symbol; returns ticket or 0
   ulong             FindPendingOrder(void) const
     {
      const int total = OrdersTotal();
      for(int i = 0; i < total; i++)
        {
         const ulong ticket = OrderGetTicket(i);
         if(ticket == 0)
            continue;
         if(OrderGetString(ORDER_SYMBOL) != m_symbol)
            continue;
         if((long)OrderGetInteger(ORDER_MAGIC) != m_magic)
            continue;
         return ticket;
        }
      return 0;
     }

   //--- only tightens the stop, never loosens; applies at most once per new bar (called from that context)
   bool              ApplyTrailing(const double atrValue, const double atrMultiplier)
     {
      if(!PositionSelect(m_symbol) || (long)PositionGetInteger(POSITION_MAGIC) != m_magic)
         return false;
      if(atrValue <= 0.0 || atrMultiplier <= 0.0)
         return false;

      const long   posType  = PositionGetInteger(POSITION_TYPE);
      const double curSL    = PositionGetDouble(POSITION_SL);
      const double tp       = PositionGetDouble(POSITION_TP);
      const double price    = (posType == POSITION_TYPE_BUY)
                               ? SymbolInfoDouble(m_symbol, SYMBOL_BID)
                               : SymbolInfoDouble(m_symbol, SYMBOL_ASK);
      const double distance = atrValue * atrMultiplier;
      const double point    = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
      const int    minStopPts = StopsLevelPoints();
      const double minDist   = (minStopPts + 1) * point;

      double newSL;
      if(posType == POSITION_TYPE_BUY)
        {
         newSL = RoundToTickSize(price - distance);
         if(newSL <= curSL)
            return false; // only move up
         if((price - newSL) < minDist)
            return false;
        }
      else
        {
         newSL = RoundToTickSize(price + distance);
         if(curSL > 0.0 && newSL >= curSL)
            return false; // only move down
         if((newSL - price) < minDist)
            return false;
        }

      if(!m_trade.PositionModify(m_symbol, newSL, tp))
        {
         if(m_logger != NULL)
            m_logger.Log(LOG_WARN, StringFormat("ApplyTrailing: PositionModify failed retcode=%d", m_trade.ResultRetcode()));
         return false;
        }
      return true;
     }

   string            LastError(void) const
     {
      return StringFormat("retcode=%d desc=%s", m_trade.ResultRetcode(), m_trade.ResultRetcodeDescription());
     }
  };
