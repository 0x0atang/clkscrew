#ifndef _GLITCH_SD805_H
#define _GLITCH_SD805_H

#include <linux/regulator/driver.h>
#include <linux/regulator/consumer.h>
#include <linux/clk/msm-clk-provider.h>

// Specify the CPU core id to pin process to.
// We only use 3 cores out of 4 to reduce noise.
#define CPU_CORE0       0
#define CPU_GLITCH      1
#define CPU_SLAVE       2
#define NUM_CPU         4


#define LOW_VCO_MAX_L_VAL    0x41

#define FUNCTYPE_SET_FREQ(x) (int (*)(struct clk *c, unsigned long rat))(x)
#define FUNCTYPE_GET_FREQ(x) (int (*)(void *data, u64 *val))(x)
#define FUNCTYPE_SET_VOLTAGE(x) (int (*)(struct regulator_dev *rdev, \
                                int min_uV, int max_uV, unsigned *selector))(x)


struct freq_volt_data {
  
  // Common
  struct kpss_core_clk *p_kpss_core_clk[NUM_CPU];
  
  // Freq-related
  struct hfpll_clk *p_hfpll_clk[NUM_CPU];
  struct measure_clk *p_measure_clk;
  u32 fptr_clock_debug_measure_get;
  u32 fptr_hfpll_clk_set_rate;
  
  struct hfpll_clk *p_hfpll_l2;
  
  // Voltage-related
  struct regulator *regulator[NUM_CPU];
  u32 fptr_krait_power_set_voltage;
};


/*
 * Copyright (c) 2013, The Linux Foundation. All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 and
 * only version 2 as published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 */
/*
 * Extracted from: msm/include/soc/qcom/clock-krait.h
 */
struct hfpll_data {
  const u32 mode_offset;
  const u32 l_offset;
  const u32 m_offset;
  const u32 n_offset;
  const u32 user_offset;
  const u32 droop_offset;
  const u32 config_offset;
  const u32 status_offset;
  
  const u32 droop_val;
  u32 config_val;
  const u32 user_val;
  u32 user_vco_mask;
  unsigned long low_vco_max_rate;
  
  unsigned long min_rate;
  unsigned long max_rate;
};

struct hfpll_clk {
  void  * __iomem base;
  struct hfpll_data const *d;
  unsigned long	src_rate;
  int		init_done;
  
  struct clk	c;
};

struct avs_data {
  unsigned long	*rate;
  u32		*dscr;
  int		num;
};

struct kpss_core_clk {
  int		id;
  u32		cp15_iaddr;
  u32		l2_slp_delay;
  struct avs_data	*avs_tbl;
  struct clk	c;
};


/* Copyright (c) 2012-2014, The Linux Foundation. All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 and
 * only version 2 as published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 */
/*
 * Extracted from: msm/include/soc/qcom/clock-local2.h
 */
/**
 * struct measure_clk - for rate measurement debug use
 * @sample_ticks: sample period in reference clock ticks
 * @multiplier: measurement scale-up factor
 * @divider: measurement scale-down factor
 * @c: clk
 */
struct measure_clk {
  u64 sample_ticks;
  u32 multiplier;
  u32 divider;
  
  struct clk c;
};


/*
 * core.c  --  Voltage/Current Regulator framework.
 *
 * Copyright 2007, 2008 Wolfson Microelectronics PLC.
 * Copyright 2008 SlimLogic Ltd.
 *
 * Author: Liam Girdwood <lrg@slimlogic.co.uk>
 *
 *  This program is free software; you can redistribute  it and/or modify it
 *  under  the terms of  the GNU General  Public License as published by the
 *  Free Software Foundation;  either version 2 of the  License, or (at your
 *  option) any later version.
 *
 */
/*
 * Extracted from: msm/drivers/regulator/core.c
 */
/*
 * struct regulator
 *
 * One for each consumer device.
 */
struct regulator {
  struct device *dev;
  struct list_head list;
  unsigned int always_on:1;
  unsigned int bypass:1;
  int uA_load;
  int min_uV;
  int max_uV;
  int enabled;
  char *supply_name;      // eg: f9016000.qcom,clock-krait-cpu1
  struct device_attribute dev_attr;
  struct regulator_dev *rdev;
  struct dentry *debugfs;
};


/* Copyright (c) 2012-2014, The Linux Foundation. All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 and
 * only version 2 as published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 */
/*
 * Extracted from: msm/arch/arm/mach-msm/krait-regulator.c
 */
enum krait_supply_mode {
  HS_MODE = REGULATOR_MODE_NORMAL,
  LDO_MODE = REGULATOR_MODE_IDLE,
};

struct krait_power_vreg {
  struct list_head        link;
  struct regulator_desc		desc;
  struct regulator_desc		adj_desc;
  struct regulator_dev		*rdev;
  struct regulator_dev		*adj_rdev;
  const char              *name;
  struct pmic_gang_vreg		*pvreg;
  int                     uV;
  int                     load;
  enum krait_supply_mode	mode;
  void __iomem            *reg_base;
  void __iomem            *mdd_base;
  int         ldo_default_uV;
  int         retention_uV;
  int         headroom_uV;
  int         ldo_threshold_uV;
  int         ldo_delta_uV;
  int         cpu_num;
  bool				ldo_disable;
  int         coeff1;
  int         coeff2;
  bool				reg_en;
  int         online_at_probe;
  bool				force_bhs;
  bool				adj;
  int         coeff1_reduction;
};


/*
 * Public prototypes
 */
int setup_vf_structs(struct freq_volt_data *g_vf_data);
void precompute_vco_val(struct hfpll_clk *h, u32 *vco_regval_hi, u32 *vco_regval_lo);
void set_voltage_all(struct freq_volt_data *g_vf_data, int uV);
void set_vco_source_raw(struct hfpll_clk *h, u32 regval);
void set_vco_source(struct hfpll_clk *h, u32 use_high_vco);
void set_clk_rate(struct hfpll_clk *h, u32 l_val);
u64 get_freq(struct freq_volt_data *g_vf_data, int cpu);

#endif //_GLITCH_SD805_H
