#ifndef _UBENCH_H
#define _UBENCH_H

#include <sys/syscall.h>        // __NR_sched_setaffinity
#include <sys/ioctl.h>          // _IOWR


///////////////////////////////////////////////////////////////////////////////
// Scheduling

// Extracted from <sched.h>
#define CPU_SETSIZE 1024
#define __NCPUBITS  (8 * sizeof (unsigned long))
typedef struct
{
   unsigned long __bits[CPU_SETSIZE / __NCPUBITS];
} cpu_set_t;

#define CPU_SET(cpu, cpusetp) \
  ((cpusetp)->__bits[(cpu)/__NCPUBITS] |= (1UL << ((cpu) % __NCPUBITS)))
#define CPU_ZERO(cpusetp) \
  memset((cpusetp), 0, sizeof(cpu_set_t))


static int setCurrentThreadAffinityMask(int pinned_cpu)
{
    cpu_set_t cpus;
    int err, syscallres;
    pid_t tid = gettid();
    
    //
    // On Android, since hotplugging is implemented, explicit configuring of
    // CPU affinity is not supported. So we need to use a syscall to set CPU
    // affinity.
    //
    CPU_ZERO(&cpus);
    CPU_SET(pinned_cpu, &cpus);
    
    syscallres = syscall(__NR_sched_setaffinity, tid, sizeof(cpus), &cpus);
    if (syscallres) {
        err = errno;
        printf("[*] ERROR: setCurrentThreadAffinityMask() failed! err=%d\n", err);
        return -1;
    }
    
    return 0;
}

static inline int getcpu() {
    int cpu, status;
    status = syscall(__NR_getcpu, &cpu, NULL, NULL);
    return (status == -1) ? status : cpu;
}

#endif // _UBENCH_H
