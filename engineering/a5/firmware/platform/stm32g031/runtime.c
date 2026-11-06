#include <stddef.h>

/* Freestanding C support: no heap, printf, OS, constructors or newlib. */
void *memset(void *destination, int value, size_t size)
{
    unsigned char *d = destination;
    while (size--) *d++ = (unsigned char)value;
    return destination;
}
void *memcpy(void *destination, const void *source, size_t size)
{
    unsigned char *d = destination;
    const unsigned char *s = source;
    while (size--) *d++ = *s++;
    return destination;
}
void __aeabi_memcpy(void *d, const void *s, size_t n) { (void)memcpy(d, s, n); }
void __aeabi_memcpy4(void *d, const void *s, size_t n) { (void)memcpy(d, s, n); }
void __aeabi_memcpy8(void *d, const void *s, size_t n) { (void)memcpy(d, s, n); }
void __aeabi_memclr(void *d, size_t n) { (void)memset(d, 0, n); }
void __aeabi_memclr4(void *d, size_t n) { (void)memset(d, 0, n); }
void __aeabi_memclr8(void *d, size_t n) { (void)memset(d, 0, n); }
void __libc_init_array(void) { }
