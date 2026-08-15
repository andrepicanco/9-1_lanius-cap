//+------------------------------------------------------------------+
//|                                                SwingSignal.mqh   |
//|   IdxSwing91 - EMA9/SMA21 regime + trigger detection (stateless) |
//+------------------------------------------------------------------+
#property strict

#include "..\Defines.mqh"
#include "..\Core\Logger.mqh"

// Bar-close shorthand used in the spec ("close[1] vs close[0]") maps onto real
// MQL5 series indices (0 = still-forming bar) as shift 1 (just-closed bar) vs
// shift 2 (bar before that) - this class always reads shift 1/2, never shift 0,
// so results never repaint.
class CSwingSignal
  {
private:
   string            m_symbol;
   ENUM_TIMEFRAMES   m_tf;
   int               m_hEMA;
   int               m_hSMA;
   CLogger          *m_logger;

public:
                     CSwingSignal(void) : m_symbol(_Symbol), m_tf(PERIOD_CURRENT),
                                           m_hEMA(INVALID_HANDLE), m_hSMA(INVALID_HANDLE), m_logger(NULL) {}

   bool              Init(const string symbol, const ENUM_TIMEFRAMES tf, const int emaPeriod,
                           const int smaPeriod, CLogger *logger)
     {
      m_symbol = symbol;
      m_tf     = tf;
      m_logger = logger;

      m_hEMA = iMA(symbol, tf, emaPeriod, 0, MODE_EMA, PRICE_CLOSE);
      // SMA21 filter disabled - trigger now uses EMA9 cross only. Kept commented for easy re-enable.
      // m_hSMA = iMA(symbol, tf, smaPeriod, 0, MODE_SMA, PRICE_CLOSE);

      if(m_hEMA == INVALID_HANDLE /* || m_hSMA == INVALID_HANDLE */)
        {
         if(m_logger != NULL)
            m_logger.Log(LOG_ERROR, "CSwingSignal::Init - failed to create EMA/SMA indicator handle(s)");
         return false;
        }
      return true;
     }

   void              Deinit(void)
     {
      if(m_hEMA != INVALID_HANDLE)
         IndicatorRelease(m_hEMA);
      // if(m_hSMA != INVALID_HANDLE)
      //    IndicatorRelease(m_hSMA);
      m_hEMA = INVALID_HANDLE;
      // m_hSMA = INVALID_HANDLE;
     }

   //--- evaluates the bar that just closed (shift 1) against the one before it (shift 2)
   bool              CheckForTrigger(ENUM_TRIGGER_DIR &dir, double &levelPrice, double &oppositeExtreme,
                                      datetime &triggerBarTime)
     {
      dir = TRIGGER_NONE;

      double ema[], /* sma[], */ close[];
      double high[], low[];

      if(CopyBuffer(m_hEMA, 0, 1, 2, ema) != 2)
         return false;
      // if(CopyBuffer(m_hSMA, 0, 1, 2, sma) != 2)
      //    return false;
      if(CopyClose(m_symbol, m_tf, 1, 2, close) != 2)
         return false;
      if(CopyHigh(m_symbol, m_tf, 1, 1, high) != 1)
         return false;
      if(CopyLow(m_symbol, m_tf, 1, 1, low) != 1)
         return false;

      // CopyBuffer/CopySeries fill index 0 = shift 1 (most recent closed bar),
      // index 1 = shift 2 (one before it) when using this (start,count) form.
      const double emaPrev = ema[1];
      const double emaLast = ema[0];
      // const double smaLast = sma[0];
      const double closePrev = close[1];
      const double closeLast = close[0];

      const bool crossedUp   = (closePrev <= emaPrev) && (closeLast > emaLast);
      const bool crossedDown = (closePrev >= emaPrev) && (closeLast < emaLast);

      if(crossedUp /* && smaLast > closeLast */)
        {
         dir             = TRIGGER_BUY;
         levelPrice      = high[0];
         oppositeExtreme = low[0];
         triggerBarTime  = iTime(m_symbol, m_tf, 1);
         return true;
        }

      if(crossedDown /* && smaLast < closeLast */)
        {
         dir             = TRIGGER_SELL;
         levelPrice      = low[0];
         oppositeExtreme = high[0];
         triggerBarTime  = iTime(m_symbol, m_tf, 1);
         return true;
        }

      return false;
     }
  };
