import os
import time
import commands
import threading
import subprocess
import pyprimes
import numpy as np
from binascii import hexlify, unhexlify

# local
import config
import utils


USR_BIN_PATH = '/usr/bin/'


# =============================================================================
# Engine classes

class Engine(object):
    """ A convenient class that coordinates all system actions.
    """
    def __init__(self, cfg):
        
        # Configuration tagged to current device
        self.cfg = cfg
        
        # Task (will be set when we create a task)
        self.task = None
        
        # Check if build environment is ready
        if not self._is_ready():
            exit()
    
    
    def _is_ready(self):
        """ Perform a self-check to ensure all the required files are present.
        
        @returns:
            True if all good.
        """
        if not os.path.exists(USR_BIN_PATH + self.cfg.ADB_PROC):
            print "[+] ERROR: <%s> tool is not available" % self.cfg.ADB_PROC
            return False 
        if not os.path.exists(USR_BIN_PATH + self.cfg.ADB_KPROC):
            print "[+] ERROR: <%s> tool is not available" % self.cfg.ADB_KPROC
            return False
        return True
    
    
    def _get_adbd_mask(self):
        os_exec_commands('adb devices')
        time.sleep(2)
        pid = self.run_adb_and_get_output('pgrep adbd')
        s = self.run_adb_and_get_output('taskset -ap %d' % pid, is_output_string=True)
        adbd_mask = s.split(' ')[-1]
        return pid, adbd_mask
    
    
    def _init_adbd_mask(self):
        pid, adbd_mask = self._get_adbd_mask()
        adb_exec_cmd_one(self.cfg.DEVICE_ID, 'taskset -ap 1 %s' % pid)
    
    
    def reboot(self):
        """ Reboot phone and prepare glitching environment for phone.
        
        Assumes that the phone has already been flashed to the required rom.
        
        @returns:
            True if reboot process is successful.
        """
        print "[+] Rebooting DEVICE ID: %s" % (self.cfg.DEVICE_ID)
        is_reboot_success = False
        while not is_reboot_success:
            time.sleep(2)
            is_timeout = True
            status = 256
            n_fb_reboot = 0
            while is_timeout or (status == 256):
                n_fb_reboot += 1
                status, output, is_timeout = \
                    ThreadExecCmd('%s -s %s reboot' % (self.cfg.ADB_PROC, self.cfg.DEVICE_ID)).run()
                time.sleep(5)
                
                if is_timeout or (status == 256):
                    print '[-]   adb reboot failed. n=%d' % n_fb_reboot
                    time.sleep(30)
                    if n_fb_reboot > 3:
                        print '\a\a\a\a\a\a\a\a\a\a'
                        utils.verbalize_reset()
                    if n_fb_reboot > 15:
                        exit()
            
            print '[+] Polling device to determine if it is live'
            time.sleep(self.cfg.INIT_TIME_BEFORE_POLLING)
            n = 0
            nproc = self.run_adb_and_get_output('ps | wc -l')
            
            while nproc < self.cfg.THRES_ACTIVE_PROC and n < 20:
                time.sleep(2)
                nproc = self.run_adb_and_get_output('ps | wc -l')
                n += 1
            if n == 20:
                print "[-]   Polling for reboot timeout. nproc=%d, n=%d" % (nproc, n)
                return False
            
            is_reboot_success = True
            
            # Something extra for Nexus 6 (shamu)
            if self.cfg.DEVICE_TYPE == config.DEV_TYPES['shamu']:
                if not self.do_shamu_preboot():
                    is_reboot_success = False
        
        
        time.sleep(self.cfg.INIT_TIME_BEFORE_POLLING)
        self.setup_prologue_stage(delay=0.5)
        time.sleep(4)
        return True
    
    
    def do_shamu_preboot(self):
        """ Specific to Nexus 6 shamu -- Need to load a prep driver.
        """
        modname = self.cfg.SOLE_GLITCH_DRV_NAME
        if self.is_mod_loaded(modname):
            print '[-]   Module is already loaded. Skipping...'
            return True
        else:
            n_tries = 0
            while not self.is_mod_loaded(modname) and n_tries < 5:
                print '[-]   Trying to load module -- n_tries:%d' % n_tries
                adb_exec_cmd_one(self.cfg.DEVICE_ID, 'insmod %s/%s.ko' % (config.DIR_REMOTE_TMP, modname))
                time.sleep(5)
                n_tries += 1
            print '[-]   Module (%s) loaded: %d' % (modname, self.is_mod_loaded(modname))
            if n_tries < 5:
                return True
        return False
    
    
    def run_adb_and_get_output(self, cmdstr, is_output_string=False):
        t = ThreadAdbCmd(self.cfg.ADB_PROC, self.cfg.DEVICE_ID, cmdstr)
        t.run()
        output = t.output
        if not is_output_string:
            if not output or not output.isdigit():
                return 0
            return int(output)
        return output
    
    
    def is_env_initialized_stage(self):
        print '[+] PROLOGUE: Checking if environment is initialized:'
        self._init_adbd_mask()
        pid, adbd_mask = self._get_adbd_mask()
        print '[-]   - ENV: adbd_mask: %s' % adbd_mask
        if not '1' in adbd_mask:
            return False
        
        for i, (c, s, o) in enumerate(self.cfg.CHECK_INIT_CMDS):
            out = self.run_adb_and_get_output(c, s)
            time.sleep(0.5)
            print '[-]   - ENV[%d] (%s): %s' % (i, c, str(out))
            if out != o:
                return False 
        
        print '[-]   Environment is initialized.'
        return True
    
    
    def setup_prologue_stage(self, delay):
        """ NOTE: Ensure that SuperSu binary is run as daemon.
        """
        if self.is_env_initialized_stage():
            return
        
        print '[+] PROLOGUE: Disabling services and CPUs:'
        tries = 0
        while not self.is_env_initialized_stage():
            print '[-]   Environment NOT initialized. Configuring...'
            adb_exec_cmd_many(self.cfg.SETUP_PROLOGUE_CMDS_STAGE1, delay, self.cfg.ADB_PROC, self.cfg.DEVICE_ID)
            time.sleep(1)
            self._init_adbd_mask()
            time.sleep(1)
            tries += 1
            if tries == 3:
                print '[-]   Device may be temporarily fried. Sleep for a while.'
                time.sleep(600)
                self.reboot()
            if tries > 5:
                print '[-] ***** Cannot initialize glitching environment! Exiting'
                exit()
        print '[-]   PROLOGUE STAGE completed'
    
    
    def is_mod_loaded(self, mod_name):
        _, output = adb_exec_cmd_one(self.cfg.DEVICE_ID, 'lsmod | grep %s' % mod_name)
        return mod_name in output
    
    
    def create_kproc_sess(self, modname):
        return ThreadKproc(modname, self.cfg.ADB_KPROC, self.cfg.DEVICE_ID, self.task)
    
    
    def exec_glitch_one_iter(self, gval, gdur, pdelay, mod_name, temperature=0):
        """ Execute our glitching module.
        """
        cmd_str = "taskset 1 /system/bin/insmod %s/%s.ko PARAM_gval=0x%x PARAM_gdelay=%d PARAM_delaypre=%d PARAM_temp=%d" % \
            (config.DIR_REMOTE_TMP, mod_name, gval, gdur, pdelay, temperature)
        return ThreadAdbCmd(self.cfg.ADB_PROC, self.cfg.DEVICE_ID, cmd_str, timeout=25)
    
    
    def regulate_temperature(self, min_temp, max_temp, sleep_time=5):
        """ @TODO: To implement
            - need to compile ubench for new phone
        """
        curr_temp = self.get_temperature()
        
        # Kill all remnants of the tool first
        adb_exec_cmd_one(self.cfg.DEVICE_ID, 'pkill -9 -f %s' %  self.cfg.FEVER_TOOL)
        time.sleep(1)
        
        # Temperature too low
        if curr_temp < min_temp:
            if self.cfg.CMD_PRE_POST_TEMPERATURE_RAMPUP:
                for c in self.cfg.CMD_PRE_POST_TEMPERATURE_RAMPUP['PRE']:
                    ThreadAdbCmd(self.cfg.ADB_PROC, self.cfg.DEVICE_ID, c, 3).run()
            while curr_temp < min_temp:
                t = ThreadAdbCmd(self.cfg.ADB_PROC, self.cfg.DEVICE_ID, self.cfg.FEVER_TOOL, timeout=sleep_time)
                t.run(is_quiet=True)
                curr_temp = self.get_temperature()
                print '[-]       Ramping up temperature: curr_temp=%d' % curr_temp
                if curr_temp == 0:
                    return False
            if self.cfg.CMD_PRE_POST_TEMPERATURE_RAMPUP:
                for c in self.cfg.CMD_PRE_POST_TEMPERATURE_RAMPUP['POST']:
                    ThreadAdbCmd(self.cfg.ADB_PROC, self.cfg.DEVICE_ID, c, 3).run()
        
        # Temperature too high
        elif curr_temp > max_temp:
            while curr_temp > max_temp - (max_temp - min_temp)/2:
                time.sleep(sleep_time)
                curr_temp = self.get_temperature()
                print '[-]       Cooling down temperature: curr_temp=%d' % curr_temp
        
        # Just in case
        adb_exec_cmd_one(self.cfg.DEVICE_ID, 'pkill -9 -f %s' %  self.cfg.FEVER_TOOL)
        print '[-]   Temperature in required range. Continuing.'
        
        return True
    
    
    def get_temperature(self):
        temp = self.run_adb_and_get_output('cat %s' % self.cfg.CPU_TEMP_LOG)
        temp = 0 if temp is None else temp
        return temp
    
    
    def do_glitch_one(self, modname, gval, gdur, pdelay, logfn, is_check_fever=True, min_temp=None):
        """ Perform one round of glitching using a set of params.
            Returns (1) if glitching round proceeded with any hitch
                    (2) if slave thread TZ invocation failed
        """
        success = True
    
        # Create thread to monitor for crashes
        thread_kproc = ThreadKproc(modname, self.cfg.ADB_KPROC, self.cfg.DEVICE_ID, self.task)
        thread_kproc.run()
        
        # Check for unstable phone conditions even before glitching
        if thread_kproc.has_terminated:
            print '[+] do_glitch_one: ERROR: cat /proc/kmsg has died.'
            success = False
        if not self.is_env_initialized_stage():
            print '[+] do_glitch_one: ERROR: Phone restarted unexpectedly.'
            success = False
        temp_min = self.cfg.MIN_TEMP
        temp_max = self.cfg.MAX_TEMP
        if min_temp is not None:
            temp_min = min_temp
            temp_max = temp_min + 1000
        if is_check_fever and not self.regulate_temperature(temp_min, temp_max):
            print '[+] do_glitch_one: ERROR: Cannot read temperature.'
            success = False
        if not success:
            thread_kproc.kill()
            dump_tz_iter_results(logfn, thread_kproc, gval, gdur, pdelay)
            return False, False, 0
        
        temperature = self.get_temperature()
        
        print '\n[+]---[ New Glitching Params ]--------------------------'
        print '[-]   gval=0x%x  gdur=%d  predelay=%d' % (gval, gdur, pdelay)
        print '[-]   CPU Temperature: %d' % temperature
        
        # Run dummy thread first to exercise the caches and pipeline
        print '[-]   +++ Step [1]: Exercise cache with dummy rounds...'
        thread_fuzz = self.exec_glitch_one_iter(self.cfg.FREQ_BASE, gdur, pdelay, modname, temperature)
        thread_fuzz.run()
        time.sleep(4)
        thread_kproc.flush_results()
        print '[-]   +++ Step [2]: Begin real glitching...'
        time.sleep(2)
        
        # Create thread to run TZ benchmark and glitch
        if not thread_fuzz.is_timeout:
            thread_fuzz = self.exec_glitch_one_iter(gval, gdur, pdelay, modname, temperature)
            thread_fuzz.run()
        
        # Oops... Phone died
        if thread_kproc.has_terminated:
            print '[+] do_glitch_one(b): ERROR: cat /proc/kmsg has died.'
            success = False
        if thread_fuzz.is_timeout:
            print '[+] do_glitch_one: ERROR: Glitching fuzz thread has timed out.'
            success = False
        if config.ERR_INSMOD_FAIL in thread_fuzz.output:
            print '[+] do_glitch_one: ERROR: Cannot load glitch fuzzing module.'
            success = False
    
        # Dump pending results
        thread_kproc.kill()
        n, istzfail, _ = dump_tz_iter_results(logfn, thread_kproc, gval, gdur, pdelay)
        print '[+] Dumping results: n=%d istzfail=%d' % (n, istzfail)
    
        # Check if we have any results
        if success and n == 0:
            print '[+] do_glitch_one: ERROR: No valid results.'
            success = False
    
        return success, istzfail, n




class ThreadAdbCmd(object):
    """ Encapsulate an ADB command so that we can trap the timeout.
    """
    def __init__(self, pname, device_id, adbcmd, timeout=10):
        self.pname = pname
        self.device_id = device_id
        self.timeout = timeout
        self.adbcmd = adbcmd
        self.is_timeout = False
        self.output = ''

    def run(self, is_quiet=False):
        def target():
           _, self.output = adb_exec_cmd_one(self.device_id, self.adbcmd, self.pname)
        
        self.thrd = threading.Thread(target=target)
        self.thrd.start()
        self.thrd.join(self.timeout)
        if self.thrd.is_alive():
            force_kill_os(self.pname)
            self.is_timeout = True
            if not is_quiet:
                print '[+] ERROR: adb cmd has timed out! Force-killing adb'
                print '[-]      (%s)' % self.adbcmd



class ThreadExecCmd(object):
    """ Encapsulate a session to execute OS-level command.
    """
    def __init__(self, cmdstr, timeout=10):
        self.timeout = timeout
        self.cmdstr = cmdstr
        self.is_timeout = False
        self.output = None
        self.status = None
        self.pname = cmdstr.split(' ')[0]

    def run(self):
        def target():
           self.status, self.output = commands.getstatusoutput(self.cmdstr)

        self.thrd = threading.Thread(target=target)
        self.thrd.start()
        self.thrd.join(self.timeout)
        if self.thrd.is_alive():
            force_kill_os(self.pname)
            self.is_timeout = True
            print '[+] ERROR: getstatusoutput cmd has timed out! Force-killing ...'
            print '[-]      (%s)' % self.cmdstr
        return self.status, self.output, self.is_timeout


class ThreadKproc(object):
    
    def __init__(self, modname, pname, dev_id, task):
        self.dev_id = dev_id
        self.pname = pname
        self.task = task
        self.proc = None
        self.thrd = None
        self.has_terminated = False
        self.iter_results = []
        self.cmd_str = 'taskset 1 /system/bin/cat /proc/kmsg | grep %s' % (modname)
        self.prevRes = None
        self.niter = 0
    
    def save_res(self, pr, iter):
        self.iter_results.append(pr)
        print '[-]   (%02d)' % (iter), pr

    def dumpRes(self):
        if self.prevRes:
            self.niter = self.niter + 1
            self.save_res(self.prevRes, self.niter)
            self.prevRes = None

    def flush_results(self):
        self.iter_results = []
        self.prevRes = None
  
    def run(self):
        def target():
            print '[+] KPROC: Monitoring /proc/kmsg for glitches'

            self.cmd_str = [self.pname, '-s', self.dev_id, 'shell', 'su', \
                            '-c', '\"%s\"' % self.cmd_str]
            self.proc = subprocess.Popen(self.cmd_str,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE,
                                         shell=False)
            while True:
                nextline = self.proc.stdout.readline()

                if nextline == '' and self.proc.poll() != None:
                    time.sleep(2)
                    self.dumpRes()
                    print '[-]   KPROC: Terminating.'
                    self.has_terminated = True
                    break

                nextline = nextline.strip()

                if 'ITER' in nextline:
                    self.dumpRes()
                    vals = nextline.split(',')
                    self.prevRes = TzIterationResult(self.task, int(vals[3], 16), int(vals[4]), int(vals[5]))
                    if vals[6].isdigit():
                        self.prevRes.add_temperature(int(vals[6]))

                # Skip until we have a valid iteration
                if self.prevRes is None:
                    continue

                if ',glitch,' in nextline:
                    vals = nextline.split(',')
                    print '  GLITCH', vals[2:]
                    if not vals or len(vals) < 3:
                        continue
                    try:
                        self.prevRes.add_glitch_stats(int(vals[2]), int(vals[3]))
                        self.prevRes.add_stats_scratch_g(vals[4])
                    except IndexError:
                        print '  GLITCH--', nextline

                if ',slave,' in nextline:
                    vals = nextline.split(',')
                    if vals[2] != 'EXPT_TEST':
                        print '  SLAVE-vals', vals[2:]
                    if vals[2] == 'FAIL' or vals[2] == 'PASS' or vals[2] == 'DONE':
                        is_pass = True if vals[2] == 'PASS' else False
                        self.prevRes.add_slave_stats(int(vals[3]),
                                                     int(vals[4]),
                                                     is_pass,
                                                     int(vals[5],16))
                        self.prevRes.add_stats_scratch_s(vals[6])
                    elif vals[2] == 'FAIL_RND':
                        print '  SLAVE-rnd', vals[3:]
                        self.prevRes.add_failrnd_stats(vals[3:])
                    elif vals[2] == 'FAIL_MOD':
                        print '  SLAVE-mod', vals[3:]
                        self.prevRes.add_failmod(vals[3:])
                    elif vals[2] == 'FAIL_CT':
                        print '  SLAVE-ct', vals[3:]
                        self.prevRes.add_failct(vals[3:])
                    elif vals[2] == 'FAIL_RRND':
                        print '  SLAVE-rrnd', vals[3:]
                        self.prevRes.add_failrrnd(vals[3:])
                    elif vals[2] == 'FAIL_MODR':
                        print '  SLAVE-modr', vals[3:]
                        self.prevRes.add_failmodr(vals[3:])
                    elif vals[2] == 'TZFAIL':
                        print '  SLAVE-tzfail', vals[3:]
                        self.prevRes.set_failure()
                    elif vals[2] == 'PROFILE':
                        print '  SLAVE-profile', vals[3:]
                        self.prevRes.add_pdelay_profile(vals[3:])
                    elif vals[2] == 'EXPT_TEST':
                        self.prevRes.add_expttest(vals[3:])
                    else:
                        raise Exception('Unexpected slave string:\n' + nextline)


        self.thrd = threading.Thread(target=target)
        self.thrd.start()

    def kill(self):
        self.dumpRes()
        force_kill_os(self.pname)


class TzIterationResult:
    def __init__(self, task, gvalue, gdelay, delaypre):
        self.task = task
        self.gvalue = gvalue
        self.gdelay = gdelay
        self.delaypre = delaypre
        self.failrnd_s = ''
        self.is_pass = None
        self.scratch_s = ''
        self.scratch_g = ''
        self.failmod_lst = []
        self.failct_lst = []
        self.failrrnd_lst = []
        self.failmodr_lst = []
        self.expttest_lst = []
        self.temperature = 0
        self.ccnt_g = 0
        self.insn_g = 0
        self.ccnt_s = 0
        self.insn_s = 0
        self.is_fail_tz = False
        
        # for pdelay profiling
        self.pdelay_stats = None

    def is_incorrect(self):
        if self.failrnd:
            return True
        return False

    def add_glitch_stats(self, ccnt_g, insn_g):
        self.ccnt_g = ccnt_g
        self.insn_g = insn_g

    def add_temperature(self, temperature):
        self.temperature = temperature

    def add_slave_stats(self, ccnt_s, insn_s, is_pass, ret_val):
        self.ccnt_s = ccnt_s
        self.insn_s = insn_s
        self.is_pass = is_pass
        self.ret_val = ret_val

    def add_stats_scratch_s(self, scratch_s):
        self.scratch_s = scratch_s.strip()

    def add_stats_scratch_g(self, scratch_g):
        # drop anchor_ccnt
        self.scratch_g = '|'.join(scratch_g.strip().split('|')[1:])

    def add_failrnd_stats(self, rnd_s):
        self.failrnd_s = ','.join(rnd_s)
    
    def add_failmod(self, mod_s):
        self.failmod_lst.extend(mod_s[1:])
    
    def add_failct(self, ct_s):
        self.failct_lst.extend(ct_s[1:])
    
    def add_failrrnd(self, rrnd_s):
        self.failrrnd_lst.extend(rrnd_s[1:])
    
    def add_failmodr(self, modr_s):
        self.failmodr_lst.extend(modr_s[1:])
    
    def add_expttest(self, expttest_s):
        self.expttest_lst.extend(expttest_s[1:])
  
    def set_failure(self):
        self.is_fail_tz = True

    def is_invalid(self):
        return self.is_pass is None

    def is_failtz(self):
        return self.is_fail_tz

    def add_pdelay_profile(self, pdelay_stats):
        self.pdelay_stats = pdelay_stats

    def get_profile_str(self):
        pass_str = 'PASS' if self.is_pass else 'FAIL'
        s = '%s, %x, %d, %d,%d,%d,%d,%s' % \
            (pass_str, self.ret_val, self.temperature, self.ccnt_s, self.insn_s,
             self.ccnt_g, self.insn_g, ','.join(self.pdelay_stats))
        return s

    def __str__(self):
        if self.is_invalid():
            return ',,,,,'
        pass_str = 'PASS' if self.is_pass else 'FAIL'
        s = '%s, %x, %d, %d,%d,%d,%d,\t%s|%s' % \
            (pass_str, self.ret_val, self.temperature, self.ccnt_s, self.insn_s,
             self.ccnt_g, self.insn_g, self.scratch_g, self.scratch_s)
        if self.failrnd_s:
            s += '\n\t\tRND:'
            s += self.failrnd_s
        if self.failct_lst:
            failct = ''.join(self.failct_lst)
            s = s + '\n\t\tCT:' + failct
        if self.failrrnd_lst:
            failrrnd = ','.join(self.failrrnd_lst)
            s = s + '\n\t\tRRND:' + failrrnd
        if self.failmodr_lst:
            failmodr = ''.join(self.failmodr_lst)
            s = s + '\n\t\tR2MODN:' + failmodr
        if self.failmod_lst:
            failstr = ''.join(self.failmod_lst)
            s = s + '\n\t\tNPRIME:' + failstr
            if self.task == config.TASK_TYPES['rsaauth'] and not '00000000' in failstr:
                s = s + '\n' + get_bitflip_stats(failstr)
        if self.expttest_lst:
            exptfail_str = ''.join(self.expttest_lst)
            s = s + '\n\t\tEXPT_STR:' + exptfail_str
            
            if self.task == config.TASK_TYPES['rsaauth'] or \
                    self.task == config.TASK_TYPES['glitchexpt']:
                s = s + '\n' + get_bitflip_stats(exptfail_str)
            if self.task == config.TASK_TYPES['glitchprof']:
                s = s + '\n' + get_expt_stats_memcpy(exptfail_str)
            """
            s = s + '\n' + get_expt_stats_memcpy(exptfail_str)
            """
        return s





# =============================================================================
# Task classes

class TaskPdelayProfiling(object):
    """ Find a range of "sweet-spot" values for pdelay using our profiling 
        technique with dual mutex.
    """
    TASK = config.TASK_TYPES['pdelayprof']
    
    def __init__(self, engine):
        self.engine = engine
        self.cfg = engine.cfg
        self.params = unserialize(self.cfg.P_PDELAY_PROFILE)
        self.modname = self.params['modname']
        self.logfn = self.params['logfn'] + self.modname + '.txt'
        self.engine.task = config.TASK_TYPES['pdelayprof']
    
    def _do_profile_one(self, modname, logfn, gval, gdur, pdelay):
        success = True
        
        # Create thread to monitor for crashes
        thread_kproc = self.engine.create_kproc_sess(modname)
        thread_kproc.run()
        
        # Check for unstable phone conditions even before glitching
        if thread_kproc.has_terminated:
            print '[+] _do_profile_one(a): ERROR: cat /proc/kmsg has died.'
            success = False
        if not self.engine.is_env_initialized_stage():
            print '[+] _do_profile_one: ERROR: Phone restarted unexpectedly.'
            success = False
        if not success:
            thread_kproc.kill()
            _, _, results = dump_tz_iter_results(logfn, thread_kproc, gval, gdur, pdelay)
            return False, False, results
        
        # Create thread to run TZ benchmark and glitch
        thread_fuzz = self.engine.exec_glitch_one_iter(gval, gdur, pdelay, modname)
        thread_fuzz.run()
         
        # Oops... Phone died
        if thread_kproc.has_terminated:
            print '[+] _do_profile_one(b): ERROR: cat /proc/kmsg has died.'
            success = False
        if thread_fuzz.is_timeout:
            print '[+] _do_profile_one: ERROR: Glitching fuzz thread has timed out.'
            success = False
        if config.ERR_INSMOD_FAIL in thread_fuzz.output:
            print '[+] _do_profile_one: ERROR: Cannot load glitch fuzzing module.'
            success = False
        
        # Dump pending results
        thread_kproc.kill()
        time.sleep(2)
        n, istzfail, results = dump_tz_iter_results(logfn, thread_kproc, gval, gdur, pdelay)
        
        # Check if we have any results
        if success and n == 0:
            print '[+] _do_profile_one: ERROR: No valid results.'
            success = False
        
        return success, istzfail, results
    
    
    def _process_res_one(self, res, pdelay, output):
        """
        GOAL: The ideal "pdelay" will minimize the time both slave and glitch have to wait
        
        RESULTS:
            ccntdelta_s: # of CYCLES slave waited for glitch to be in position
            timeout_s:   # of LOOP epochs slave waited
            ccntdelta_g: # of CYCLES glitch waited for slave to complete workload
            timeout_g:   # of LOOP epochs glitch waited
        
        NOTES:
            - If timeout_s or timeout_g == 0x40000, it means the extreme 
              ranges are hit and thus the respective ccnt may be inaccurate.
            - Two "opposing" forces,
                - To decrease <ccntdelta_s> => Decrease <pdelay>
                - To decrease <ccntdelta_g> => Increase <pdelay>
        
        ALGO:
            - Search for pdelay values where timeout_s and timeout_g are non-zero
        
        KEY FEATURES:
            - Use timeout instead of ccnt => more stable
            - Use more iterations
            - Use IQR mean
        """
        ll = []
        if pdelay in output:
            ll = output[pdelay]
        
        for r in res:
            (ccntdelta_s, timeout_s, ccntdelta_g, timeout_g) = map(lambda x:int(x), r)
            metric = np.sqrt(timeout_s**2 + timeout_g**2)
            print (ccntdelta_s, hex(timeout_s), ccntdelta_g, hex(timeout_g)), \
                  pdelay, np.sqrt(ccntdelta_s**2 + ccntdelta_g**2), metric
            ll.append(metric)
        
        output[pdelay] = ll
    
    
    def _do_profile(self, pdelay, output):
        """ Given pdelay, returns IQR mean of metric.
        """
        for i in xrange(self.params['nb_iter']):
            for t in xrange(self.params['nb_tries']):
                
                print '\n[+]======[Iter %d - Try %d]========' % (i+1, t+1)
                time.sleep(5)
                
                success, istzfail, results = \
                    self._do_profile_one(self.modname, self.logfn, 
                                         self.cfg.FREQ_BASE, 1, pdelay)
                
                # Proceed to next iteration if we succeed
                if success:
                    break
                
                # If slave thread failed, try again without rebooting
                if istzfail:
                    print '[-]   Slave seemed to have failed in TZ'
                    continue
                
                # For unsuccessful round, we'll reset the phone
                while not self.engine.reboot():
                    print '[-]   Reboot failed. Try again!'
            
            # Compute the new pdelay value to try
            new_pdelay = self._process_res_one(results, pdelay, output)
        
        return utils.iqr_mean(output[pdelay])
    
    
    def run(self, eps=1):
        
        # Store global list {pdelay : list of metrics}
        output = {}
        
        # Perform a binary scan of the pdelay values until a specific threshold
        pdelay_lo = self.params['pdelay']['BASE']
        pdelay_hi = self.params['pdelay']['END']
        
        metric_lo = self._do_profile(pdelay_lo, output)
        metric_hi = self._do_profile(pdelay_hi, output)
        diff = np.abs(metric_hi - metric_lo)
        n = 0
        n_stagnate = 0
        
        while (diff > eps) and (n_stagnate < 3):
            print '\n*** [%d] [%d, %d]: %f, %f (%f)' % (n, pdelay_lo, pdelay_hi, metric_lo, metric_hi, diff)
            n += 1
            
            pdelay_curr = (pdelay_lo + pdelay_hi) / 2
            metric_curr = self._do_profile(pdelay_curr, output)
            
            # Assume that our binary scan will monotonically reduce metric 
            # between a given range
            if metric_curr > metric_lo and metric_curr > metric_hi:
                print 'ERROR: metric_curr (%f) is out of range!' % metric_curr
                print 'Try again: n_stagnate=%d' % n_stagnate
                n_stagnate += 1
                continue
            
            if np.mean([metric_lo, metric_curr]) < np.mean([metric_curr, metric_hi]):
                pdelay_hi = pdelay_curr
                metric_hi = metric_curr
            else:
                pdelay_lo = pdelay_curr
                metric_lo = metric_curr
            
            diff = np.abs(metric_hi - metric_lo)
        
        print '--------------------------------'
        pdelays = sorted(list(output.viewkeys()))
        for p in pdelays:
            ll = output[p]
            print 'pdelay=%d => %f' % (p, utils.iqr_mean(ll))


class TaskGlitchProfiling(object):
    """ Find a range of {pdelay, gval, gdur} that causes glitches to different
        workloads.
    """
    TASK = config.TASK_TYPES['glitchprof']
    
    def __init__(self, engine):
        self.engine = engine
        self.cfg = engine.cfg
        self.params = unserialize(self.cfg.P_GLITCH_PROFILE)
        self.modname = self.params['modname']
        self.logfn = self.params['logfn'] + self.modname + '.txt'
        self.engine.task = config.TASK_TYPES['glitchprof']
    
    def run(self):
        for gval in xrange_tuple(self.params, 'gval'):
            for gdur in xrange_tuple(self.params, 'gdur'):
                for pdelay in xrange_tuple(self.params, 'pdelay'):
                    for i in xrange(self.params['nb_iter']):
                        for t in xrange(self.params['nb_tries']):
                            print '\n[+]======[Iter %d - Try %d]==========' % (i, t)
                            time.sleep(2)
                            
                            success, istzfail, _ = \
                                self.engine.do_glitch_one(self.modname, gval, gdur, pdelay, self.logfn)
                            
                            # If slave thread failed, try again without rebooting
                            if istzfail:
                                print '[-]   Slave seemed to have failed in TZ'
                                continue
    
                            # Proceed to next iteration if we succeed
                            if success:
                                break
    
                            # For unsuccessful round, we'll reset the phone
                            while not self.engine.reboot():
                                print '[-]   Reboot failed. Try again!'


class TaskGlitchRsa(object):
    """ Find a range of {pdelay, gval, gdur} that causes glitches to different
        workloads.
    """
    TASK = config.TASK_TYPES['rsaauth']
    
    def __init__(self, engine):
        self.engine = engine
        self.cfg = engine.cfg
        self.params = unserialize(self.cfg.P_GLITCH_RSA)
        self.modname = self.params['modname']
        self.logfn = self.params['logfn'] + self.modname + '.txt'
        self.engine.task = config.TASK_TYPES['rsaauth']
    
    def run(self):
        for gval in xrange_tuple(self.params, 'gval'):
            for gdur in xrange_tuple(self.params, 'gdur'):
                for pdelay in xrange_tuple(self.params, 'pdelay'):
                    for i in xrange(self.params['nb_iter']):
                        for t in xrange(self.params['nb_tries']):
                            print '\n[+]======[Iter %d - Try %d]==========' % (i, t)
                            time.sleep(2)
                            
                            success, istzfail, _ = \
                                self.engine.do_glitch_one(self.modname, gval, gdur, pdelay, self.logfn)
                            
                            # If slave thread failed, try again without rebooting
                            if istzfail:
                                print '[-]   Slave seemed to have failed in TZ'
                                continue
    
                            # Proceed to next iteration if we succeed
                            if success:
                                break
    
                            # For unsuccessful round, we'll reset the phone
                            while not self.engine.reboot():
                                print '[-]   Reboot failed. Try again!'


class TaskGlitchExpt(object):
    """ Explore various parameter ranges to compare glitching rates.
    """
    TASK = config.TASK_TYPES['glitchexpt']
    NUM_ITER = 50
    
    def __init__(self, engine):
        self.engine = engine
        self.cfg = engine.cfg
        self.params = unserialize(self.cfg.P_GLITCH_EXPT)
        self.modname = self.params['modname']
        self.logfn = self.params['logfn'] + self.modname + '.txt'
        self.engine.task = config.TASK_TYPES['glitchexpt']
    
    def run(self):
        for temp in xrange_tuple(self.params, 'temp'):
            for gval in xrange_tuple(self.params, 'gval'):
                for gdur in xrange_tuple(self.params, 'gdur'):
                    for pdelay in xrange_tuple(self.params, 'pdelay'):
                        i = 0
                        while True:
                            print '\n[+]======[n = %d]==========' % (i)
                            time.sleep(2)
                            
                            success, istzfail, n = \
                                self.engine.do_glitch_one(self.modname, gval, gdur, pdelay, self.logfn, min_temp=temp)
                            
                            # If slave thread failed, try again without rebooting
                            if istzfail:
                                print '[-]   Slave seemed to have failed in TZ'
                                continue
    
                            # Proceed to next set of parameters
                            i += n
                            if i > self.NUM_ITER:
                                break
    
                            # For unsuccessful round, we'll reset the phone
                            while not self.engine.reboot():
                                print '[-]   Reboot failed. Try again!'



# =============================================================================
# Misc utils


def dump_tz_iter_results(fn, thread_kproc, gvalue, gdelay, predelay):
    n = 0
    is_failtz = False
    results = []
    with open(fn, 'a') as fh:
        for iterRes in thread_kproc.iter_results:
            if iterRes.is_failtz():
                is_failtz = True
                break
            if iterRes.pdelay_stats is not None:
                fh.write('0x%x,%d,%d,%s\n' % (gvalue, gdelay, predelay, iterRes.get_profile_str()))
                n += 1
                results.append(list(iterRes.pdelay_stats))
                continue
            if not iterRes.is_invalid():
                fh.write('0x%x,%d,%d,%s\n' % (gvalue, gdelay, predelay, iterRes))
                n += 1
                continue
    thread_kproc.iter_results  = []
    return n, is_failtz, results


def unserialize(p):
    for k, v in p.iteritems():
        if isinstance(v, dict):
            for param_k, param_v in v.iteritems():
                if isinstance(param_v, list):
                    vv = param_v
                else:
                    vv = int(param_v, 16) if '0x' in param_v else int(param_v)
                v[param_k] = vv
            p[k] = v
        else:
            if isinstance(v, basestring) and v.isdigit():
                p[k] = int(param_v, v) if '0x' in v else int(v)
            else:
                p[k] = v
    return p


def serialize(p):
    q = {}
    for k, v in p.iteritems():
        if isinstance(v, dict):
            vvv = {}
            for param_k, param_v in v.iteritems():
                if param_k == 'BASE' or \
                   param_k == 'END' or \
                   param_k == 'LAST':
                    vv = hex(param_v)
                elif param_k == 'OTHER':
                    vv = param_v
                else:
                    vv = str(param_v)
                vvv[param_k] = vv
            q[k] = vvv
        else:
            q[k] = v
    return q


def xrange_tuple(p, type):
    base = 'LAST' if p['resume'] else 'BASE'
    r = range(p[type][base], p[type]['END'] + 1, p[type]['STEP'])
    if 'OTHER' in p[type]:
        r.extend(p[type]['OTHER'])
    return r


def os_exec_subprocess(c_lst):
    p = subprocess.Popen(c_lst, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.wait(), p.stdout.read(), p.stderr.read()


def os_exec_commands(cmd_str):
    """ subprocess.Popen cannot execute commands like "echo 1 > ...". As a
        workaround, we use the commands.getstatusoutput API.

        The limitation is this technique cannot return the success status of
        the adb shell command within the device.
    """
    n_tries = 0
    while n_tries < 10:
        status, output = commands.getstatusoutput(cmd_str)
        if not status:
            return output
        if not 'error: device not found' in output and \
           not 'error: protocol fault (no status)' in output:
            break
        n_tries += 1
        time.sleep(5)

        if n_tries == 10:
            print '[-] ****os_exec_commands:', status, output
            print cmd_str
            print '[-]   os_exec_commands: phone likely offline. Exiting.'
            exit()

    print '[-]   os_exec_commands: FAILED: status: %d (%s)' % (status, output)
    print '[-]       (%s)' % cmd_str


def force_kill_os(pname):
    _, cnt, _ = os_exec_subprocess(['pkill', '-c', '-9', '-f', pname])
    cnt = cnt.rstrip()
    if cnt and cnt.isdigit():
        if int(cnt) == 0:
            print '[-]   force_kill_os: FAILED: Did not kill process <%s>' % pname
        elif int(cnt) > 1:
            print '[-]   force_kill_os: FAILED: Kill more than 1 instance of <%s>: %d' % (pname, int(cnt))
    else:
        print '[-]   force_kill_os: ERROR: Unexpected output:', cnt


def adb_exec_cmd_one(device_id, cmd_str, adb_proc='adb'):
    if 'echo' in cmd_str:
        full_cmd = '%s -s %s shell su -c \"%s\"' % (adb_proc, device_id, cmd_str)
        return 0, os_exec_commands(full_cmd)

    n_tries = 0
    while n_tries < 10:
        ret, s_out, s_err = \
            os_exec_subprocess([adb_proc, '-s', device_id, 'shell', 'su', \
                                '-c', '\"%s\"' % cmd_str])
        
        output = s_err if not s_out else s_out
        if not 'error: device not found' in output and \
           not 'daemon not running' in output and \
           not 'error: protocol fault (no status)' in output:
            break
        n_tries += 1
        time.sleep(5)

        if n_tries == 10:
            print '[-] ***adb_exec_cmd_one: <%s> <%s> <%s>' % (output, s_out, s_err)
            print ' '.join([adb_proc, '-s', device_id, 'shell', 'su', \
                            '-c', '\"%s\"' % cmd_str])

    if n_tries == 10:
        print '[-]   adb_exec_cmd_one: phone likely offline. Exiting.'
        exit()
    return ret, output.strip()


def adb_exec_cmd_many(cmd_lst_str, delay, adb_proc, device_id):
    is_error = True
    while is_error:
        is_error = False
        for c in cmd_lst_str:
            print '[-]   Bulk execing: ', c
            t = ThreadAdbCmd(adb_proc, device_id, c)
            t.run()
            if t.is_timeout:
                is_error = True
                print '[-]   ERROR: cannot adb_exec: ', c
            time.sleep(delay)
        if is_error:
            print '[-]  ERROR: cannot execute bulk cmds. Continuing'



#------------------------------------------------------------------------------
# Prime checks and bit flips

def hex2bin(s):
    if len(s) % 2:
        s = '0' + s
    h = '\x00'
    try:
        h = unhexlify(s)
    except Exception:
        print 'hex2bin() err:', s
    return h


def get_bitflip_stats(new):
    mod_orig = """\
c44dc735f6682a261a0b8545a62dd13df4c646a5ede482cef858925baa1811fa0284766b3d1d2b4
d6893df4d9c045efe3e84d8c5d03631b25420f1231d8211e2322eb7eb524da6c1e8fb4c3ae4a8f5
ca13d1e0591f5c64e8e711b3726215cec59ed0ebc6bb042b917d44528887915fdf764df691d183e
16f31ba1ed94c84b476e74b488463e85551022021763af35a64ddf105c1530ef3fcf7e54233e5d3
a4747bbb17328a63e6e3384ac25ee80054bd566855e2eb59a2fd168d3643e44851acf0d118fb03c
73ebc099b4add59c39367d6c91f498d8d607af2e57cc73e3b5718435a81123f080267726a2a9c1c
c94b9c6bb6817427b85d8c670f9a53a777511b
"""
    ori = hex2bin(mod_orig.replace('\n', ''))
    new = hex2bin(new)
    s = '\t\t\tPRIME,' + str(pyprimes.isprime(int(hexlify(new), 16))) + '\n'
    for i in xrange(len(ori)):
        c1 = ord(ori[i])
        c2 = ord(new[i])
        bf = c1 ^ c2
        if bf:
            s += '\t\t\tBF,'
            s += '%d,%x,%x,%x,%d\n' % (i, c1, c2, bf, bin(bf).count('1'))
    return s[:-1]


def get_expt_stats_memcpy(new):
    """ memcpy workload
    """
    BUFLEN = 0x1000
    print new
    new = hex2bin(new)
    s = ''
    for i in xrange(BUFLEN):
        c1 = i % 256
        c2 = ord(new[i])
        bf = c1 ^ c2
        if bf:
            s += '\t\t\tBF,'
            s += '%d,%x,%x,%x,%d\n' % (i, c1, c2, bf, bin(bf).count('1'))
    return s[:-1]
        