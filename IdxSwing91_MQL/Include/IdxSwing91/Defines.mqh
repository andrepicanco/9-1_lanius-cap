//+------------------------------------------------------------------+
//|                                                    Defines.mqh   |
//|                          IdxSwing91 - enums and shared constants |
//+------------------------------------------------------------------+
#property strict

#define IDXSWING91_VERSION "1.00"

enum ENUM_TRIGGER_DIR
  {
   TRIGGER_NONE = 0,
   TRIGGER_BUY  = 1,
   TRIGGER_SELL = 2
  };

enum ENUM_EA_STATE
  {
   STATE_IDLE = 0,
   STATE_PENDING,
   STATE_IN_POSITION
  };

enum ENUM_LOG_LEVEL
  {
   LOG_DEBUG = 0,
   LOG_INFO  = 1,
   LOG_WARN  = 2,
   LOG_ERROR = 3
  };
