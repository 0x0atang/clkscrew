#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>     // _SC_NPROCESSORS_ONLN
#include <fcntl.h>      // O_RDONLY
#include <sys/mman.h>   // PROT_READ
#include "dofever.h"


#define CPU_MAIN    0
#define CPU_GLITCH  1
#define CPU_SLAVE   4

static inline double workload_complex_math_local(void)
{
  int i, j;
  double ret2 = 0;
  double ret = 1.000000000000001;
  const double constant = 8.881091e+278;
  
  for (i = 0; i < 2000000; i++) {
    for (j = 0; j < 59; j++) {
      ret *= ret;
    }
    for (j = 0; j < 59; j++) {
      ret /= ret;
    }
    ret2 += ret;
  }
  
  return ret2 - 2000000.0;
}

static inline double benchmark_complex_math_sled(double seed)
{
  return workload_complex_math_local() + seed;
}


static inline int workload_recursive_br_6(unsigned int a1,
                                          unsigned int a2,
                                          unsigned int a3,
                                          unsigned int a4,
                                          unsigned int a5,
                                          unsigned int a6)
{
  if (a1 == 0)
    return 1;
  if (a2 == 0)
    return 1;
  return workload_recursive_br_6(a1 - 1, a2, a3, a4, a5, a6) +
    workload_recursive_br_6(a1, a2 - 1, a3, a4, a5, a6);
}

static inline int benchmark_recursive_branches_6(double seed)
{
  return workload_recursive_br_6(seed, 3, 00, 11, 22, 33);
}

void stress_test_multi(void *data)
{
  volatile double ret;
  int core = *(int *)data;
  
  if (setCurrentThreadAffinityMask(core))
    return;
  sched_yield();
  
  while (1) {
    ret = benchmark_complex_math_sled(rand() % 20);
    ret = benchmark_recursive_branches_6(0x600);
    printf("%d\n", core);
  }
}


///////////////////////////////////////////////////////////////////////////////
// MAIN
//

int main(int argc, char** argv)
{
  pthread_t t1, t2, t3, t4, t5, t6, t7, t8, t9, t10;
  int c1=CPU_MAIN, c2=CPU_GLITCH, c3=CPU_SLAVE;
  int c4=CPU_MAIN, c5=CPU_GLITCH, c6=CPU_SLAVE;
  int s2=2, s3=3, s5=5, s6=6, s7=7;
  void *func;
  
  // Pin main thread to CPU 0
  setCurrentThreadAffinityMask(CPU_MAIN);
  sched_yield();
  
  // Run multiple threads of complex workload
  func = (void *) &stress_test_multi;
  pthread_create(&t1, NULL, func, &c1);
  pthread_create(&t2, NULL, func, &c2);
  pthread_create(&t3, NULL, func, &c3);
  pthread_create(&t4, NULL, func, &c4);
  pthread_create(&t5, NULL, func, &s2);
  pthread_create(&t6, NULL, func, &s3);
  pthread_create(&t7, NULL, func, &s5);
  pthread_create(&t8, NULL, func, &s6);
  pthread_create(&t9, NULL, func, &s7);
  pthread_create(&t10, NULL, func, &c6);
  pthread_join(t1, NULL);
  pthread_join(t2, NULL);
  pthread_join(t3, NULL);
  pthread_join(t4, NULL);
  pthread_join(t5, NULL);
  pthread_join(t6, NULL);
  pthread_join(t7, NULL);
  pthread_join(t8, NULL);
  pthread_join(t9, NULL);
  pthread_join(t10, NULL);
  
  return 0;
}
