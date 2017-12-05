#include <linux/module.h>
#include <linux/kallsyms.h>
#include <linux/io.h>
#include <linux/delay.h>

#include "debug.h"
#include "glitch_sd805.h"



////////////////////////////////////////////////////////////////////////////////
// Clock-related
//

#define LOCK_BIT	BIT(16)

// Initialize a HFPLL at a given rate and enable it
static void __hfpll_clk_init_once(struct hfpll_clk *h)
{
  struct hfpll_data const *hd = h->d;
  
  if (likely(h->init_done))
    return;
  
  // Configure PLL parameters for integer mode
  // atang: what is integer mode?
  if (hd->config_val)
    writel_relaxed(hd->config_val, h->base + hd->config_offset);
  writel_relaxed(0, h->base + hd->m_offset);
  writel_relaxed(1, h->base + hd->n_offset);
  
  if (hd->user_offset) {
    u32 regval = hd->user_val;
    unsigned long rate;
    
    rate = readl_relaxed(h->base + hd->l_offset) * h->src_rate;
    
    // Pick the right VCO
    if (hd->user_vco_mask && rate > hd->low_vco_max_rate)
      regval |= hd->user_vco_mask;
    writel_relaxed(regval, h->base + hd->user_offset);
  }
  
  if (hd->droop_offset)
    writel_relaxed(hd->droop_val, h->base + hd->droop_offset);
  
  h->init_done = true;
}

// Enable an already-configured HFPLL
static int hfpll_clk_enable(struct hfpll_clk *h)
{
  struct hfpll_data const *hd = h->d;
  
  if (!h->base)
    return -ENODEV;
  
  __hfpll_clk_init_once(h);
  
  // Disable PLL bypass mode
  writel_relaxed(0x2, h->base + hd->mode_offset);
  
  // H/W requires a 5us delay between disabling the bypass and
  // de-asserting the reset. Delay 10us just to be safe.
  mb();
  udelay(10);
  
  // De-assert active-low PLL reset
  writel_relaxed(0x6, h->base + hd->mode_offset);
  
  // Wait for PLL to lock
  if (hd->status_offset) {
    while (!(readl_relaxed(h->base + hd->status_offset) & LOCK_BIT))
      ;
  } else {
    mb();
    udelay(60);
  }
  
  // Enable PLL output
  writel_relaxed(0x7, h->base + hd->mode_offset);
  
  // Make sure the enable is done before returning
  mb();
  
  return 0;
}

// Disable the PLL output, disable test mode, enable the bypass mode,
// and assert the reset.
static void hfpll_clk_disable(struct hfpll_clk *h)
{
  struct hfpll_data const *hd = h->d;
  writel_relaxed(0, h->base + hd->mode_offset);
}


///////////////////////////////////////////////////////////////////////////////
// Voltage-related
//
static int set_voltage(struct freq_volt_data *g_vf_data, int cpu, int uV)
{
  int dummy;
  
  return (FUNCTYPE_SET_VOLTAGE(g_vf_data->fptr_krait_power_set_voltage))
        (g_vf_data->regulator[cpu]->rdev, uV, uV, &dummy);
}



///////////////////////////////////////////////////////////////////////////////
// Misc
//

static unsigned long kallsyms_find_symbol(char *name)
{
  return (unsigned long)kallsyms_lookup_name(name);
}


///////////////////////////////////////////////////////////////////////////////
// Public methods
//

int setup_vf_structs(struct freq_volt_data *g_vf_data)
{
  int i;
  
  
  // Common
  if ( (!(g_vf_data->p_kpss_core_clk[0] =
          (struct kpss_core_clk *)(kallsyms_find_symbol("krait0_clk")))) ) {
    DBG("[thread_glitch]: Cannot get required symbols!\n");
    return -1;
  }
  DBG2("[thread_glitch]: krait0_clk: 0x%x\n", (u32)(g_vf_data->p_kpss_core_clk[0]));
  
  for (i = 1; i < NUM_CPU; i++) {
    g_vf_data->p_kpss_core_clk[i] =
      (struct kpss_core_clk *)((u32)(g_vf_data->p_kpss_core_clk[0]) + i * 0x6c);
    DBG2("[thread_glitch]: p_kpss_core_clk:[%d] 0x%x\n", i,
        (u32)(g_vf_data->p_kpss_core_clk[i]));
  }
  
  
  // Frequency
  if ( (!(g_vf_data->p_measure_clk =
          (struct measure_clk *)(kallsyms_find_symbol("measure_clk")))) ) {
    DBG("[thread_glitch]: Cannot get required symbols!\n");
    return -1;
  }
  DBG2("[thread_glitch]: measure_clk:0x%x  c:0x%x\n",
      (u32)(g_vf_data->p_measure_clk), (u32)&g_vf_data->p_measure_clk->c);
  
  if ( (!(g_vf_data->p_hfpll_clk[0] = (struct hfpll_clk *)(kallsyms_find_symbol("hfpll0_clk")))) ) {
    DBG("[thread_glitch]: Cannot get required symbols!\n");
    return -1;
  }
  DBG2("[thread_glitch]: p_hfpll_clk: 0x%x\n", (u32)(g_vf_data->p_hfpll_clk[0]));
  
  for (i = 1; i < NUM_CPU; i++) {
    g_vf_data->p_hfpll_clk[i] = (struct hfpll_clk *)((u32)(g_vf_data->p_hfpll_clk[0]) + i * 0x6c);
    DBG2("[thread_glitch]: p_hfpll_clk:[%d] 0x%x\n", i, (u32)(g_vf_data->p_hfpll_clk[i]));
  }
  
  if ( (!(g_vf_data->fptr_clock_debug_measure_get = (kallsyms_find_symbol("clock_debug_measure_get")))) ) {
    DBG("[thread_glitch]: Cannot get required symbols!\n");
    return -1;
  }
  
  if ( (!(g_vf_data->p_hfpll_l2
          = (struct hfpll_clk *)(kallsyms_find_symbol("hfpll_l2_clk")))) ) {
    DBG("[thread_glitch]: Cannot get required symbols!\n");
    return -1;
  }
  DBG2("[thread_glitch]: p_hfpll_l2: 0x%x\n", (u32)(g_vf_data->p_hfpll_l2));
  
  
  if ( (!(g_vf_data->fptr_hfpll_clk_set_rate
          = (kallsyms_find_symbol("hfpll_clk_set_rate")))) ) {
    DBG("[thread_glitch]: Cannot get required symbols!\n");
    return -1;
  }
  
  
  // Voltage
  if ( (!(g_vf_data->fptr_krait_power_set_voltage
          = (kallsyms_find_symbol("krait_power_set_voltage")))) ) {
    DBG("[thread_glitch]: Cannot get required symbols!\n");
    return -1;
  }
  
  for (i = 0; i < NUM_CPU; i++) {
    g_vf_data->regulator[i] = g_vf_data->p_kpss_core_clk[i]->c.vdd_class->regulator[0];
    DBG2("[thread_glitch]: regulator (%s): 0x%x\n", g_vf_data->regulator[i]->supply_name, (u32)g_vf_data->regulator[i]);
    DBG2("[thread_glitch]:   - min_uV: %d  max_uV: %d\n", g_vf_data->regulator[i]->min_uV, g_vf_data->regulator[i]->max_uV);
  }
  
  return 0;
}


// Pre-compute VCO source regval for speed
void precompute_vco_val(struct hfpll_clk *h, u32 *vco_regval_hi, u32 *vco_regval_lo)
{
  struct hfpll_data const *hd = h->d;
  u32 regval = readl_relaxed(h->base + hd->user_offset);
  
  *vco_regval_hi = regval | hd->user_vco_mask;
  *vco_regval_lo = regval & ~hd->user_vco_mask;
}


void set_vco_source_raw(struct hfpll_clk *h, u32 regval)
{
  struct hfpll_data const *hd = h->d;
  writel_relaxed(regval, h->base  + hd->user_offset);
}


// Select VCO source (low or high rate VCO)
void set_vco_source(struct hfpll_clk *h, u32 use_high_vco)
{
  struct hfpll_data const *hd = h->d;
  u32 regval = readl_relaxed(h->base + hd->user_offset);
  
  if (use_high_vco)
    regval |= hd->user_vco_mask;
  else
    regval &= ~hd->user_vco_mask;
  writel_relaxed(regval, h->base  + hd->user_offset);
}


// Configure VCO PLL using the multiplier l value
// ***BUG*** if used directly, the effect is not reflected in the real measurements!
void set_clk_rate(struct hfpll_clk *h, u32 l_val)
{
  struct hfpll_data const *hd = h->d;
  writel_relaxed(l_val, h->base + hd->l_offset);
}


void set_voltage_all(struct freq_volt_data *g_vf_data, int uV)
{
  int i;
  
  for (i = 0; i < NUM_CPU - 1; i++) {
    if (set_voltage(g_vf_data, i, uV)) {
      DBG("[thread_glitch]: ERROR: Cannot set voltage for CPU %d!\n", i);
    }
  }
}


u64 get_freq(struct freq_volt_data *g_vf_data, int cpu)
{
  u64 val;
  int ret;
  
  ret = (FUNCTYPE_GET_FREQ(g_vf_data->fptr_clock_debug_measure_get))
    (&g_vf_data->p_kpss_core_clk[cpu]->c, &val);
  if (ret != 0)
    val = -1;
  
  return val;
}
