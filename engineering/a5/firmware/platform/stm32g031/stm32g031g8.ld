ENTRY(Reset_Handler)
MEMORY
{
    FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 64K
    RAM (xrw) : ORIGIN = 0x20000000, LENGTH = 8K
}
_estack = ORIGIN(RAM) + LENGTH(RAM);
_Min_Stack_Size = 2048;
SECTIONS
{
    .isr_vector : { . = ALIGN(4); KEEP(*(.isr_vector)) . = ALIGN(4); } > FLASH
    .text :
    {
        . = ALIGN(4);
        *(.text*) *(.rodata*)
        KEEP(*(.init)) KEEP(*(.fini))
        . = ALIGN(4);
        _etext = .;
    } > FLASH
    .ARM.extab : { *(.ARM.extab*) } > FLASH
    .ARM.exidx : { __exidx_start = .; *(.ARM.exidx*); __exidx_end = .; } > FLASH
    _sidata = LOADADDR(.data);
    .data :
    {
        . = ALIGN(4); _sdata = .;
        *(.data*)
        . = ALIGN(4); _edata = .;
    } > RAM AT > FLASH
    .bss (NOLOAD) :
    {
        . = ALIGN(4); _sbss = .;
        *(.bss*) *(COMMON)
        . = ALIGN(4); _ebss = .;
    } > RAM
    .stack_reserve (NOLOAD) :
    {
        . = ALIGN(8); _end = .;
        . += _Min_Stack_Size;
    } > RAM
    /DISCARD/ : { *(.comment) *(.note*) }
}
ASSERT(_ebss + _Min_Stack_Size <= _estack, "RAM overflow: reserve at least 2KiB stack")
