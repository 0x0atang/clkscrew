#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/kthread.h>
#include <linux/semaphore.h>
#include <linux/delay.h>
#include <asm/cacheflush.h>

#include "debug.h"
#include "memalloc.h"
#include "workload.h"
#include "glitch_sd805.h"


// Specific the CPU core id to pin process to
#define CPU_CORE0       0
#define CPU_GLITCH      1
#define CPU_SLAVE       2
#define NUM_CPU         4


// Tag prefix for failure cases
#define ERR_TAG       "EXPT_TEST"


///////////////////////////////////////////////////////////////////////////////
// Command-line params

//
// CONFIG: Don't glitch before this iteration (Set to 0 to disable)
//
#define MIN_GLITCH_ITER       3

#define DUMMY_GLITCH_FREQ     0x88
#define PARAM_GLITCH_VOLT     1055000
#define GLITCH_FREQ_SAFE      0x90

// Number of iteration per settings
static int PARAM_iter = MIN_GLITCH_ITER + 5;

// Amplitude of glitch frequency
static int PARAM_gval = DUMMY_GLITCH_FREQ;

// Length of glitch
static int PARAM_gdelay = 1;

// Pre-glitch delay
static int PARAM_delaypre = 1;

// Temperature
static int PARAM_temp = 0;

// Base clamping voltage
static int PARAM_volt = PARAM_GLITCH_VOLT;

// User-supplied parameters from insmod
module_param(PARAM_gval, int, 0);
module_param(PARAM_gdelay, int, 0);
module_param(PARAM_delaypre, int, 0);
module_param(PARAM_iter, int, 0);
module_param(PARAM_temp, int, 0);
module_param(PARAM_volt, int, 0);


///////////////////////////////////////////////////////////////////////////////
// Globals

// To manage glitching of voltage and frequency
struct freq_volt_data g_vf_data;

typedef struct _glitch_params {
  int v;                // voltage
  int fl;               // freq base
  int fh;               // freq glitch value
  int d1;               // glitch duration
  int d0;               // pre-glitch delay
  int i;                // iteration
  void *workload;       // function to be executed by slave thread
} glitch_params_t;

static struct task_struct *task_main = NULL;
static struct task_struct *task_glitch = NULL;
static struct task_struct *task_slave = NULL;

static glitch_params_t g_glitch_params = {0};

typedef struct _scratch {
  u32 s_to_ns_mutex;
} scratch_t;

// Semaphores to coordinate cross-core glitching
static DEFINE_SEMAPHORE(sem_glitch_begin);
static DEFINE_SEMAPHORE(sem_slave_begin);
static DEFINE_SEMAPHORE(sem_thread_end);
static DEFINE_SEMAPHORE(sem_main_end);

// SLAVE => GLITCH: start glitching
static int start_glitch;

// SLAVE => MAIN: signal end of computation
static volatile int end_slave;

static inline void set_mutex(void *mutex, u32 val);
static inline u32 lock_mutex_ro(void *mutex);

// global test buffers
static payload_buf_t g_buf_dst = {0};
static payload_buf_t g_buf_src = {0};

// global scratch data
static scratch_t g_scratch = {0};

// global workload function pointer
static payload_buf_t g_workload = {0};



///////////////////////////////////////////////////////////////////////////////
// Misc

static void hexprint_type(u8 *ptr, u32 len, char *type)
{
  int i;
  for (i = 0; i < len; i += 0x40) {
    if (len - i < 0x40)
      DBG("| ,slave,%s,%d,%*phN\n", type, i/0x40, len - i, ptr + i);
    else
      DBG("| ,slave,%s,%d,%*phN\n", type, i/0x40, 0x40, ptr + i);
  }
}

static inline void __delay_loop(unsigned long loops)
{
  asm volatile(
               "1:	subs %0, %0, #1 \n"
               "	  bhi 1b		\n"
               : // no output
               : "r" (loops)
               );
}

//
// Get currently executing core using MPIDR register
//
static inline u32 get_cpu_id(void)
{
  u32 value;
  asm volatile ("mrc p15, 0, %0, c0, c0, 5\n\t" : "=r"(value));
  return value & 0x0f;
}

static inline void set_mutex(void *mutex, u32 val)
{
  asm volatile(
               "dmb \n"
               "mov   r0, %[val] \n"
               "str   r0, [%[mutex]] \n"
               "dsb   st \n"
               "sev \n"
               : // no output
               : [mutex]"r" (mutex), [val]"r" (val)
               : "r0"
               );
}

static inline u32 lock_mutex_ro(void *mutex)
{
  u32 val;
  asm volatile(
               "1: ldrex   r0, [%[mutex]] \n"
               "   cmp     r0, #0 \n"
               "   beq     1b \n"
               "   mov     %[val], r0 \n"
               : [val]"=r" (val)
               : [mutex]"r" (mutex)
               : "r0"
               );
  return val;
}


//
// Prepare the base voltage/frequency settings for the slave thread, before we
// begin glitching. This ensures consistency for our glitching thread.
//
// IMPORTANT: Assume that the following commands have been run:
//    stop thermal-engine
//    stop mpdecision
//    echo 1 > /sys/devices/system/cpu/cpu1/online
//    echo 1 > /sys/devices/system/cpu/cpu2/online
//    echo 0 > /sys/devices/system/cpu/cpu3/online
//    echo userspace > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
//    echo userspace > /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor
//    echo userspace > /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor
//    echo 2649600 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed
//    echo 2649600 > /sys/devices/system/cpu/cpu1/cpufreq/scaling_setspeed
//    echo 2649600 > /sys/devices/system/cpu/cpu2/cpufreq/scaling_setspeed
//
static void init_base_volt_freq_slave(u32 freq_lo, u32 vco) {
  u32 vco_regval_hi, vco_regval_lo, vco_regval;
  
  precompute_vco_val(g_vf_data.p_hfpll_clk[CPU_SLAVE], &vco_regval_hi,
                     &vco_regval_lo);
  vco_regval = (freq_lo > LOW_VCO_MAX_L_VAL) ? vco_regval_hi : vco_regval_lo;
  set_vco_source_raw(g_vf_data.p_hfpll_clk[CPU_SLAVE], vco_regval);
  set_clk_rate(g_vf_data.p_hfpll_clk[CPU_SLAVE], freq_lo);
  
  // Use the same voltage for all cores
  set_voltage_all(&g_vf_data, vco);
}


///////////////////////////////////////////////////////////////////////////////
// Stubs for ARM-thumb code invocation switch

static inline u32 __thumb_call_arg3(u32 funcptr, u32 a1, u32 a2, u32 a3)
{
  u32 ret;
  u32 fp = funcptr + 1;
  
  asm volatile(
               "mov     r2, %[a3] \n"
               "mov     r1, %[a2] \n"
               "mov     r0, %[a1] \n"
               "blx     %[fp] \n"
               "mov     %[ret], r0 \n"
               : [ret]"=r" (ret)
               : [fp]"r" (fp), [a1]"r" (a1), [a2]"r" (a2), [a3]"r" (a3)
               : "r0", "r1", "r2", "r3"
               );
  return ret;
}



////////////////////////////////////////////////////////////////////////////////
// Specific workloads


static int verify_result(void *src, const void *ans, u32 len)
{
  u32 i;
  for (i = 0; i < len; i+=4) {
    if (*(u32 *)(src + i) != *(u32 *)(ans + i))
      return -1;
  }
  return 0;
}

static int prepare_inputs(void)
{
  //
  // NOTE: We use uncacheable DMA memory here to simulate the use of such memory
  //       in the QSEE OS.
  //
  if ((alloc_payload(&g_buf_dst, BUFTYPE_DMA, IOMEM_BUF1)) ||
      (alloc_payload(&g_buf_src, BUFTYPE_DMA, IOMEM_BUF2))) {
    DBG("[main]: ERROR: Cannot alloc test buffers failed!\n");
    return -1;
  };
  memcpy(g_buf_src.va, (u8 *)ref_modulus_orig, BUFLEN_FLIPENDIAN);
  
  return 0;
}


static inline int do_workload_args3(void *func, u32 arg1, u32 arg2, u32 arg3)
{
  int ret = __thumb_call_arg3((u32)func, arg1, arg2, arg3);
  return ret;
}


//
// THREAD FUNCTION: Perform cross-core glitching
//
static int thread_glitch_cross(void *data)
{
  unsigned long flags;
  u32 vco_regval_hi, vco_regval_lo, vco_regval;
  
  // Local glitch params
  u32 param_pre_delay = g_glitch_params.d0;
  u32 param_freq_hi = g_glitch_params.fh;
  u32 param_freq_lo = g_glitch_params.fl;
  u32 param_duration = g_glitch_params.d1;

  
  // Pre-compute vco source reg values
  precompute_vco_val(g_vf_data.p_hfpll_clk[CPU_SLAVE], &vco_regval_hi,
                     &vco_regval_lo);
  
  // Initialize voltage to something that can handle both lo and hi freqs
  vco_regval = (g_glitch_params.fl > LOW_VCO_MAX_L_VAL) ?
                vco_regval_hi : vco_regval_lo;
  set_vco_source_raw(g_vf_data.p_hfpll_clk[CPU_SLAVE], vco_regval);
  set_voltage_all(&g_vf_data, g_glitch_params.v);
  
  // Initialize frequency to base value
  set_clk_rate(g_vf_data.p_hfpll_clk[CPU_SLAVE], param_freq_lo);
  
  // Wait for glitch thread to be ready to enter critical section
  down(&sem_glitch_begin);
  
  // Disable preemption
  local_fiq_disable();
  local_irq_save(flags);
  
  // Flush
  flush_cache_all();
  
  // Wait for slave thread to run first
  rmb();
  lock_mutex_ro(&start_glitch);
  
  rmb();
  lock_mutex_ro(&g_scratch.s_to_ns_mutex);
  
  // Pre delay
  __delay_loop(param_pre_delay);
  
  
  ////////////
  // glitching BEGIN
  
  set_clk_rate(g_vf_data.p_hfpll_clk[CPU_SLAVE], param_freq_hi);
  __delay_loop(param_duration);
  wmb();
  set_clk_rate(g_vf_data.p_hfpll_clk[CPU_SLAVE], param_freq_lo);
  
  // glitching END
  ////////////
  
  
  mb();
  local_irq_restore(flags);
  local_fiq_enable();
  
  up(&sem_thread_end);
  return 0;
}

//
// THREAD FUNCTION: Slave workload
//
static int thread_slave_workload(void *data)
{
  u32 *iter = (u32 *)data;
  u32 ret = 0;
  unsigned long flags;
  size_t len;
  
  
  down(&sem_slave_begin);
  local_fiq_disable();
  local_irq_save(flags);
  
  // Exercise cache (if required)
  flush_cache_all();
  
  // Initialize scratchpad
  memset(&g_scratch, 0, sizeof(scratch_t));
  wmb();
  
  // Signal glitch thread that slave thread is ready
  set_mutex(&start_glitch, 1);
  
  // prologue
  __delay_loop(WORKLOAD_PREMUTEX);
  set_mutex(&g_scratch.s_to_ns_mutex, 1);
  
  
  ///////////////////// Payload START
  
  __delay_loop(WORKLOAD_PREDELAY);
  len = BUFLEN_FLIPENDIAN;
  ret = do_workload_args3(g_workload.va, (u32)g_buf_dst.va, (u32)g_buf_src.va,
                          len);
  
  ///////////////////// Payload END
  
  
  // epilogue
  __delay_loop(WORKLOAD_POSTDELAY);
  
  // Restore IRQs
  local_irq_restore(flags);
  local_fiq_enable();
  
  if (*iter >= MIN_GLITCH_ITER) {
    if (verify_result(g_buf_dst.va, ref_modulus_rev, len)) {
      DBG("| ,slave,FAIL\n");
      hexprint_type(g_buf_dst.va, len, ERR_TAG);
    } else {
      DBG("| ,slave,PASS\n");
    }
  }
    
  // Signal main thread that slave thread is completed to stop cache flushing
  end_slave = 1;
  wmb();
  
  up(&sem_thread_end);
  return ret;
}


////////////////////////////////////////////////////////////////////////////////
// Generic to workloads

//
// THREAD FUNCTION: Initialize glitch and slave threads.
//
static int thread_main_init_glitch(void *data)
{
  glitch_params_t *glitch_params = (glitch_params_t *)data;
  u32 *iter = NULL;
  
  
  //DBG("[thread_main]:  Running in core: %d\n", get_cpu_id());
  
  // Set up volt/freq parameters to be used in the glitch thread
  memcpy(&g_glitch_params, glitch_params, sizeof(glitch_params_t));
  iter = kzalloc(sizeof(u32), GFP_KERNEL);
  if (!iter) {
    DBG("[thread_main]:  ERROR allocating memory\n");
    return -1;
  }
  *iter = glitch_params->i;
  
  if (*iter >= MIN_GLITCH_ITER) {
    DBG("|---- ,ITER-%02d,0x%2x,%d,%d,%d,%d\n",
        glitch_params->i - MIN_GLITCH_ITER, glitch_params->fh,
        glitch_params->d1, glitch_params->d0, PARAM_temp, glitch_params->v);
  }
  
  // Initialize base voltage and frequency in slave core
  init_base_volt_freq_slave(glitch_params->fl, glitch_params->v);
  
  // Initialize SLAVE => GLITCH synchronizing signal
  set_mutex(&start_glitch, 0);
  
  // Initialize SLAVE => MAIN synchronizing signal
  end_slave = 0;
  wmb();
  
  // Initialize glitch thread and pin to one CPU core
  if (cpu_online(CPU_GLITCH)) {
    task_glitch = kthread_create(thread_glitch_cross, iter, "thread_glitch");
    if (IS_ERR(task_glitch)) {
      DBG("[main]: Cannot create task_glitch.\n");
      return -1;
    }
    kthread_bind(task_glitch, CPU_GLITCH);
    wake_up_process(task_glitch);
  } else {
    DBG("[main]: Core %d not online.\n", CPU_GLITCH);
    return -1;
  }
  
  // Initialize slave thread and pin to one CPU core
  if (cpu_online(CPU_SLAVE)) {
    task_slave = kthread_create(glitch_params->workload, iter, "thread_slave");
    if (IS_ERR(task_slave)) {
      DBG("[main]: Cannot create thread_slave.\n");
      return -1;
    }
    kthread_bind(task_slave, CPU_SLAVE);
    wake_up_process(task_slave);
  } else {
    DBG("[main]: Core %d not online.\n", CPU_SLAVE);
    return -1;
  }
  
  // Signal both threads to start
  up(&sem_glitch_begin);
  up(&sem_slave_begin);
  
  // Constantly flush the cache while slave is running
  rmb();
  while (!end_slave) {
    flush_cache_all();
  }
  
  // Wait for both threads
  down(&sem_thread_end);
  down(&sem_thread_end);
  
  // Signal end of this thread
  up(&sem_main_end);
  
  if (iter)
    kzfree(iter);
  
  return 0;
}

//
// Schedule the main coordination thread to run on CPU0 so that we can have the
// glitching and slave thread on the other two cores. This reduces the chance of
// our coordination thread being glitched.
//
static int do_cross_glitch(void *workload_func)
{
  u32 i;
  glitch_params_t *glitch_params = NULL;
  glitch_params_t *dummy_glitch_params = NULL;
  glitch_params_t *active_glitch_params;
  
  
  // Initialize all semaphores
  sema_init(&sem_glitch_begin, 0);
  sema_init(&sem_slave_begin, 0);
  sema_init(&sem_thread_end, 0);
  sema_init(&sem_main_end, 0);
  
  glitch_params = kzalloc(sizeof(glitch_params_t), GFP_KERNEL);
  dummy_glitch_params = kzalloc(sizeof(glitch_params_t), GFP_KERNEL);
  if ((!glitch_params) || (!dummy_glitch_params)) {
    DBG("[do_cross_glitch]:  glitch_params kzalloc failed!\n");
    return -1;
  }
  
  glitch_params->v = PARAM_volt;
  glitch_params->fl = GLITCH_FREQ_SAFE;
  glitch_params->fh = PARAM_gval;
  glitch_params->d1 = PARAM_gdelay;
  glitch_params->d0 = PARAM_delaypre;
  glitch_params->workload = workload_func;
  
  memcpy(dummy_glitch_params, glitch_params, sizeof(glitch_params_t));
  dummy_glitch_params->fh = DUMMY_GLITCH_FREQ;
  
  for (i = 0; i < PARAM_iter; i++) {
    
    active_glitch_params = (i < MIN_GLITCH_ITER) ?
      dummy_glitch_params : glitch_params;
    active_glitch_params->i = i;
    
    if (cpu_online(CPU_CORE0)) {
      task_main = kthread_create(thread_main_init_glitch, active_glitch_params,
                                 "glitchmin_core0_main");
      if (IS_ERR(task_main)) {
        DBG("[do_cross_glitch]: Cannot create task_main.\n");
        return -1;
      }
      kthread_bind(task_main, CPU_CORE0);
      wake_up_process(task_main);
    } else {
      DBG("[do_cross_glitch]: Core %d not online.\n", CPU_CORE0);
      return -1;
    }
    down(&sem_main_end);
    if (i < PARAM_iter - 1)
      msleep(1000);
  }
  
  // Sleep a while to let system catch up on all pending tasks
  msleep(2000);
  
  if (glitch_params)
    kzfree(glitch_params);
  if (dummy_glitch_params)
    kzfree(dummy_glitch_params);
  return 0;
}


///////////////////////////////////////////////////////////////////////////////
// Module initialization

int init_module(void)
{
  if (num_online_cpus() < NUM_CPU - 1)
    goto _EXIT;
  
  if (setup_vf_structs(&g_vf_data))
    goto _EXIT;
  
  if (prepare_inputs())
    goto _EXIT;
  
  if (alloc_payload(&g_workload, BUFTYPE_VMALLOC, 0))
    goto _EXIT;
  memcpy(g_workload.va, code__flip_endianness, sizeof(code__flip_endianness));

  
  // Perform glitching exercise
  if (do_cross_glitch(thread_slave_workload))
    goto _EXIT;

_EXIT:
  
  cleanup_module();
  
  // Prevent persistent loading of module
  return -1;
}


void cleanup_module(void)
{
  free_payload(&g_buf_src);
  free_payload(&g_buf_dst);
  free_payload(&g_workload);
  
  DBG("------[ END ]------\n");
}


MODULE_LICENSE("GPL v2");
MODULE_AUTHOR("Adrian Tang");
MODULE_DESCRIPTION("CLK Glitch Profiling Driver");
MODULE_VERSION("1.0");
