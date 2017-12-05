#ifndef _DEBUG_H
#define _DEBUG_H

#define MODULE_NAME     "glitchmin"

////////////////////////
// CONFIG: Enable debugging logs
//
#define DEBUG_L1
//#define DEBUG_L2


#ifdef DEBUG_L1
#define DBG(...) do { printk(KERN_INFO MODULE_NAME ": " __VA_ARGS__);} while(0)
#else
#define DBG(...) do {} while (0)
#endif

#ifdef DEBUG_L2
#define DBG2(...) do { printk(KERN_INFO MODULE_NAME ": " __VA_ARGS__);} while(0)
#else
#define DBG2(...) do {} while (0)
#endif

#endif //_DEBUG_H
