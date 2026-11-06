#include "board.h"

static lb_controller_t light_block;

int main(void)
{
    /* CMSIS SystemInit does not clear RCC_CSR. Capture before HAL initialization. */
    lb_debug_reset_csr = RCC->CSR;
    board_reset_safe_outputs();
    if (!board_init()) board_fail(LB_FAULT_INIT);
    lb_boot_decision_t boot = board_boot_decision(lb_debug_reset_csr);
    lb_calibration_t calibration = lb_calibration_default(*VREFINT_CAL_ADDR);
    lb_io_t io = board_io();
    uint32_t now = HAL_GetTick();
    lb_controller_init(&light_block, &io, &calibration, boot, now);
    board_attach_controller(&light_block);
    uint32_t last_sample = now - 1u;
    for (;;) {
        now = HAL_GetTick();
        if (now != last_sample) {
            last_sample = now;
            uint16_t cv = 0, vref = 0;
            if (!board_adc_pair(&cv, &vref)) lb_guard_trip(&light_block.guard, LB_FAULT_ADC);
            else (void)lb_controller_adc(&light_block, cv, vref, now);
            lb_controller_step(&light_block, board_switch_ab(), now);
            board_watchdog_feed();
        }
        __WFI(); /* Sleep only until the next SysTick, DMA or FAULT interrupt. */
    }
}
