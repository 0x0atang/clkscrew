#ifndef _MEMALLOC_H
#define _MEMALLOC_H

#include <linux/dma-mapping.h>
#include <linux/vmalloc.h>
#include <linux/slab.h>


// These two hardcoded memory addresses do not seem to be used. We will retrofit
// them for "IO" memory.
#define IOMEM_BUF1      0x0F200000
#define IOMEM_BUF2      0x0F300000


// Buffer type
enum buffer_type_t {
  BUFTYPE_KZALLOC = 1,
  BUFTYPE_DMA,
  BUFTYPE_VMALLOC,
  BUFTYPE_IOMEM
};


// Payload struct to contain information for each payload buffer. Transparently
// allow allocation and freeing of buffer of different types.
typedef struct payload_buf {
  void *va;
  u32 pa;
  u32 len;
  u32 type;
} payload_buf_t;


static int alloc_payload(payload_buf_t *payload_buf, u32 type, u32 iomem_pa)
{
  const static u32 len = PAGE_SIZE;
  
  switch (type) {
    case BUFTYPE_KZALLOC:
      payload_buf->va = kzalloc(len, GFP_KERNEL);
      break;
      
    case BUFTYPE_DMA:
      payload_buf->va = dma_zalloc_coherent(NULL, len, &payload_buf->pa, GFP_KERNEL);
      break;
    
    case BUFTYPE_VMALLOC:
      payload_buf->va = __vmalloc(len, GFP_KERNEL, PAGE_KERNEL_EXEC);
      break;
      
    case BUFTYPE_IOMEM:
      payload_buf->va = ioremap_nocache(iomem_pa, len);
      payload_buf->pa = iomem_pa;
      break;
  }
  if (!payload_buf->va)
    return -1;
  
  payload_buf->type = type;
  payload_buf->len = len;
  return 0;
}


static void free_payload(payload_buf_t *payload_buf)
{
  if (!(payload_buf->va) || (payload_buf->len == 0))
    return;
  
  switch (payload_buf->type) {
    case BUFTYPE_KZALLOC:
      kzfree(payload_buf->va);
      break;
      
    case BUFTYPE_DMA:
      dma_free_coherent(NULL, payload_buf->len, payload_buf->va, payload_buf->pa);
      break;
      
    case BUFTYPE_VMALLOC:
      vfree(payload_buf->va);
      break;
      
    case BUFTYPE_IOMEM:
      iounmap(payload_buf->va);
      break;
  }
  payload_buf->va = NULL;
  payload_buf->pa = 0;
  payload_buf->len = 0;
}

#endif //_MEMALLOC_H
