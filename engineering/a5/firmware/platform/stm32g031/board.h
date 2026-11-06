#ifndef LB_STM32_BOARD_H
#define LB_STM32_BOARD_H
#include "light_block.h"
#include "stm32g0xx_hal.h"

/* These are debug-visible, read-only diagnostics, not control/arming registers. */
extern volatile uint32_t lb_debug_reset_csr;
extern volatile uint32_t lb_debug_boot_decision;
extern volatile uint32_t lb_debug_backup_at_boot[2];
extern volatile uint32_t lb_debug_adc_raw;
extern volatile uint32_t lb_debug_vref_raw;
extern volatile uint32_t lb_debug_fault;

void board_reset_safe_outputs(void);
bool board_init(void);
lb_io_t board_io(void);
lb_boot_decision_t board_boot_decision(uint32_t reset_csr);
void board_attach_controller(lb_controller_t *controller);
bool board_adc_pair(uint16_t *cv, uint16_t *vref);
uint8_t board_switch_ab(void);
void board_watchdog_feed(void);
_Noreturn void board_fail(lb_fault_t reason);
#endif
