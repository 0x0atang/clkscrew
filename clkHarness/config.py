
# Device types
dev_types = [
    ('angler',        0),
    ('shamu',         1) ]
DEV_TYPES = dict([(e[1], e[0]) for e in dev_types] + dev_types)

# Task types
task_types = [
    ('pdelayprof',        0),
    ('glitchprof',        1),
    ('rsaauth',           2),
    ('glitchexpt',        3),
    ]
TASK_TYPES = dict([(e[1], e[0]) for e in task_types] + task_types)


# Local directories
DIR_LOG = 'log'
DIR_SESSION = 'session'

# Writable directory on device
DIR_REMOTE_TMP = '/data/local/tmp'

# Error message when insmod fails
ERR_INSMOD_FAIL = 'Function not implemented'


# =============================================================================
class ConfigNexus6P():
    """ DEVICE: Huawei Nexus 6P
    """
    
    # Device type
    DEVICE_TYPE = DEV_TYPES['angler']
    
    # Device ID
    DEVICE_ID = '-'
    
    # Filename of <adb> tool - for general adb uses
    ADB_PROC = DEVICE_ID + 'adb'
    
    # Filename of <adb> tool - for tracking /proc/kmsg (Keep separate copies of
    # adb so that we selectively pkill the one we need.
    ADB_KPROC = DEVICE_ID + 'kproc'
    
    # To detect if device is fully booted up, we track the number of processes
    THRES_ACTIVE_PROC = 409
    
    # Time to wait for phone before we start to polling for the liveness
    INIT_TIME_BEFORE_POLLING = 32
    
    # Sleep time before initializing commands
    TIME_BEFORE_INIT_CMD = 10
    
    # Temperature ranges
    MIN_TEMP = 36000
    MAX_TEMP = 38000
    
    # Filename of tool to ramp up temperatures
    FEVER_TOOL = '/data/local/tmp/dofever-v8a'
    
    # Temperature sensor log
    CPU_TEMP_LOG = '/sys/devices/virtual/thermal/thermal_zone0/temp'
    
    # Commands to check that environment is initialized
    # (cmd, is_output_string, expected_output)
    CHECK_INIT_CMDS = [
        ('cat /sys/devices/system/cpu/cpu2/online', False, 0),
        ('cat /sys/devices/system/cpu/cpu4/online', False, 1),
        ('cat /sys/devices/system/cpu/cpu5/online', False, 0),
        ('cat /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor', True, 'userspace'),
        ('cat /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor', True, 'userspace'),
        ('cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq', False, 1555200),
        ('cat /sys/devices/system/cpu/cpu4/cpufreq/scaling_cur_freq', False, 960000),
        ('cat /sys/module/msm_thermal/core_control/enabled', False, 0), ]
    
    # Commands to initialize environment
    SETUP_PROLOGUE_CMDS_STAGE1 = [
        'stop thermal-engine',
        'echo 1 > /sys/kernel/debug/msm_vidc/disable_thermal_mitigation',
        'echo 0 > /sys/module/msm_thermal/vdd_mx/enabled',
        'echo 0 > /sys/module/msm_thermal/core_control/enabled',
        'echo 0 > /d/cpr-regulator/apc0_corner/cpr_enable',
        'echo 0 > /d/cpr-regulator/apc1_corner/cpr_enable',
        'echo 1 > /d/regulator/pmi8994_boostbypass/enable',
        'echo 1 > /sys/devices/system/cpu/cpu0/online',
        'echo 1 > /sys/devices/system/cpu/cpu1/online',
        'echo 0 > /sys/devices/system/cpu/cpu2/online',
        'echo 0 > /sys/devices/system/cpu/cpu3/online',
        'echo 1 > /sys/devices/system/cpu/cpu4/online',
        'echo 0 > /sys/devices/system/cpu/cpu5/online',
        'echo 0 > /sys/devices/system/cpu/cpu6/online',
        'echo 0 > /sys/devices/system/cpu/cpu7/online',
        'echo userspace > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor',
        'echo userspace > /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor',
        'echo 1555200 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed',
        'echo 960000 > /sys/devices/system/cpu/cpu4/cpufreq/scaling_setspeed',
        'echo 0 > /proc/sys/kernel/randomize_va_space' ]
    
    # Commands to help ramp up temperatures
    CMD_PRE_POST_TEMPERATURE_RAMPUP = {
        'PRE': [ 'echo 1 > /sys/devices/system/cpu/cpu2/online',
                 'echo 1 > /sys/devices/system/cpu/cpu3/online',
                 'echo 1 > /sys/devices/system/cpu/cpu5/online',
                 'echo 1 > /sys/devices/system/cpu/cpu6/online',
                 'echo 1 > /sys/devices/system/cpu/cpu7/online' ],
        'POST':[ 'echo 0 > /sys/devices/system/cpu/cpu2/online',
                 'echo 0 > /sys/devices/system/cpu/cpu3/online',
                 'echo 0 > /sys/devices/system/cpu/cpu5/online',
                 'echo 0 > /sys/devices/system/cpu/cpu6/online',
                 'echo 0 > /sys/devices/system/cpu/cpu7/online' ]
        }
    
    # Base dummy freq gval
    FREQ_BASE = 0x65
    
    P_PDELAY_PROFILE = {
        'pdelay':{
                'BASE': '85000',
                'END':  '88000',
                'STEP': '1',
                'LAST': '1'
                },
        'resume':False,
        'nb_iter':'10',
        'nb_tries':'5',
        'modname':'clkscrew',
        'logfn': DIR_LOG + '/' + 'pdprof_' + DEVICE_ID + '_'
        }
    
    P_GLITCH_PROFILE = {
        'gval':{
                'BASE': '0xa0',    #0x78
                'END':  '0xf0',    #0x98
                'STEP': '4',
                'LAST': '0x6a'
                },
        'gdur':{
                'BASE': '5',
                'END':  '11',
                'STEP': '5',
                'LAST': '2'
                },
        'pdelay':{
                'BASE': '83000',
                'END':  '90000',
                'STEP': '500',
                'LAST': '1'
                },
        'resume':False,
        'nb_iter':'5',
        'nb_tries':'2',
        'modname':'clkscrew',
        'logfn': DIR_LOG + '/' + 'glitch_prof_' + DEVICE_ID + '_'
        }
    

# =============================================================================
class ConfigNexus6():
    """ DEVICE: Motorola Nexus 6
    """
    
    # Device type
    DEVICE_TYPE = DEV_TYPES['shamu']
    
    # Device ID
    DEVICE_ID = '-'
    
    # Filename of <adb> tool - for general adb uses
    ADB_PROC = DEVICE_ID + 'adb'
    
    # Filename of <adb> tool - for tracking /proc/kmsg (Keep separate copies of
    # adb so that we selectively pkill the one we need.
    ADB_KPROC = DEVICE_ID + 'kproc'
    
    # To detect if device is fully booted up, we track the number of processes
    THRES_ACTIVE_PROC = 250
    
    # Time to wait for phone to get initialized
    INIT_TIME_BEFORE_POLLING = 15
    
    # Sleep time before initializing commands
    TIME_BEFORE_INIT_CMD = 3
    
    # Temperature ranges
    MIN_TEMP = 37000
    MAX_TEMP = 38000
    
    # Filename of tool to ramp up temperatures
    FEVER_TOOL = '/data/local/tmp/dofever-v7a'
    
    # Temperature sensor log
    CPU_TEMP_LOG = '/sys/devices/virtual/thermal/thermal_zone0/temp'
    
    # Prep kernel module. We need this module to prepare the voltages and freq
    # for all the cores before glitching.
    # @TODO: Can be removed and directly integrated into the glitching module
    SOLE_GLITCH_DRV_NAME = 'powerplay_glitch_sole'
    
    # Commands to check that environment is initialized
    # (cmd, is_output_string, expected_output)
    CHECK_INIT_CMDS = [
        ('cat /sys/devices/system/cpu/cpu3/online', False, 0),
        ('cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor', True, 'userspace'),
        ('cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_setspeed', False, 2649600),
        ('cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed', False, 2649600) ]
    
    # Commands to initialize environment
    SETUP_PROLOGUE_CMDS_STAGE1 = [
        'stop thermal-engine',
        'stop mpdecision',
        'echo 1 > /sys/devices/system/cpu/cpu1/online',
        'echo 1 > /sys/devices/system/cpu/cpu2/online',
        'echo 0 > /sys/devices/system/cpu/cpu3/online',
        'echo userspace > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor',
        'echo userspace > /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor',
        'echo userspace > /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor',
        'echo 2649600 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed',
        'echo 2649600 > /sys/devices/system/cpu/cpu1/cpufreq/scaling_setspeed',
        'echo 2649600 > /sys/devices/system/cpu/cpu2/cpufreq/scaling_setspeed',
        'echo 0 > /proc/sys/kernel/randomize_va_space',
        'sleep 0.5',
        'echo 0x5a > /sys/powerplay/freq_l2',
        'sleep 0.5',
        'echo 0x5a > /sys/powerplay/freq_all',
        'sleep 0.5',
        'echo 1055000 > /sys/powerplay/volt_all',
        'sleep 0.5',
        'echo 0x8a > /sys/powerplay/freq_all' ]
    
    # Commands to help ramp up temperatures
    CMD_PRE_POST_TEMPERATURE_RAMPUP = {}
    
    # Base dummy freq gval
    FREQ_BASE = 0x88
    
    P_PDELAY_PROFILE = {
        'pdelay':{
                'BASE': '2000',
                'END':  '12000',
                'STEP': '1',
                'LAST': '1'
                },
        'resume':False,
        'nb_iter':'10',
        'nb_tries':'5',
        'modname':'clkpeer',
        'logfn': DIR_LOG + '/' + 'pdprof_' + DEVICE_ID + '_'
        }
    
    P_GLITCH_PROFILE = {
        'gval':{
                'BASE': '0xd0',    #0x78
                'END':  '0xd0',    #0x98
                'STEP': '4',
                'LAST': '0xcc'
                },
        'gdur':{
                'BASE': '1',
                'END':  '1',
                'STEP': '1',
                'LAST': '1'
                },
        'pdelay':{
                'BASE': '4000', #35500
                'END':  '7000', #63000
                'STEP': '200',
                'LAST': '1'
                },
        'resume':False,
        'nb_iter':'5',
        'nb_tries':'3',
        'modname':'clkpeer',
        'logfn': DIR_LOG + '/' + 'glitch_prof_' + DEVICE_ID + '_'
        }
    
    P_GLITCH_RSA = {
        'gval':{
                'BASE': '0xd0',    #0x78
                'END':  '0xd0',    #0x98
                'STEP': '4',
                'LAST': '0xcc'
                },
        'gdur':{
                'BASE': '5',
                'END':  '5',
                'STEP': '20',
                'LAST': '1'
                },
        'pdelay':{
                'BASE': '8000', #35500
                'END':  '8000', #63000
                'STEP': '200',
                'LAST': '1'
                },
        'resume':False,
        'nb_iter':'20',
        'nb_tries':'3',
        'modname':'clkpeer',
        'logfn': DIR_LOG + '/' + 'glitch_rsaauth_' + DEVICE_ID + '_'
        }
    
    P_GLITCH_EXPT = {
        'gval':{
                'BASE': '0xd0',    #0x78
                'END':  '0xe0',    #0x98
                'STEP': '8',
                'LAST': '0xcc'
                },
        'gdur':{
                'BASE': '5',
                'END':  '55',
                'STEP': '25',
                'LAST': '1',
                'OTHER': [1]
                },
        'pdelay':{
                'BASE': '8000', #35500
                'END':  '8000', #63000
                'STEP': '200',
                'LAST': '1'
                },
        'temp':{
                'BASE': '39000', #35500
                'END':  '39000', #63000
                'STEP': '2000',
                'LAST': '1'
                },
        'resume':False,
        'nb_iter':'20',
        'nb_tries':'3',
        'modname':'glitchmin',
        'logfn': DIR_LOG + '/' + 'glitch_expt_' + DEVICE_ID + '_'
        }


# Configs
CONFIGS = [ConfigNexus6P, ConfigNexus6]