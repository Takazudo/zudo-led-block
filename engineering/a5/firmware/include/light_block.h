#ifndef LIGHT_BLOCK_H
#define LIGHT_BLOCK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "lb_config.h"

typedef enum { LB_MODE_INVALID = 0, LB_MODE_ON = 1, LB_MODE_CV = 2,
               LB_MODE_PROGRAM = 3 } lb_mode_t;
typedef struct { uint8_t r, g, b; } lb_rgb_t;
typedef struct { lb_rgb_t chain[LB_CHAINS][LB_PIXELS_PER_CHAIN]; } lb_frame_t;

typedef struct {
    uint8_t candidate;
    uint8_t stable;
    uint32_t candidate_since;
} lb_switch_t;
void lb_switch_init(lb_switch_t *sw, uint32_t now);
lb_mode_t lb_switch_update(lb_switch_t *sw, uint8_t ab, uint32_t now);

typedef struct {
    int32_t zero_code_q16;    /* A5 nominal 4095*50/133 codes; replace after measurement. */
    uint32_t gain_q16;        /* Correction to A5 nominal inverse ADC gain 266/25. */
    uint16_t vrefint_cal;     /* Factory 12-bit sample at VDDA=3000 mV. */
} lb_calibration_t;
lb_calibration_t lb_calibration_default(uint16_t factory_vrefint_cal);
bool lb_adc_to_cv(const lb_calibration_t *cal, uint16_t adc_code,
                  uint16_t vref_code, int32_t *cv_mv, uint32_t *vdda_mv);
void lb_render(lb_frame_t *frame, lb_mode_t mode, int32_t cv_mv,
               uint32_t now_ms);
void lb_frame_black(lb_frame_t *frame);
bool lb_ws_encode(const lb_frame_t *frame, uint16_t *interleaved,
                  size_t capacity_words);

/* Normalized reset causes. The STM32 port maps actual RCC_CSR symbols to these. */
enum {
    LB_RESET_POWER = 1u << 0, LB_RESET_PIN = 1u << 1,
    LB_RESET_SOFTWARE = 1u << 2, LB_RESET_IWDG = 1u << 3,
    LB_RESET_WWDG = 1u << 4, LB_RESET_OPTION = 1u << 5,
    LB_RESET_LOWPOWER = 1u << 6
};
typedef enum {
    LB_BOOT_COLD_CANDIDATE, LB_BOOT_LOCKED_RESET_CAUSE,
    LB_BOOT_LOCKED_RETAINED, LB_BOOT_LOCKED_CORRUPT
} lb_boot_decision_t;
typedef enum { LB_MARK_BOOT = 0x4c420101u, LB_MARK_ARMED = 0x4c420102u,
               LB_MARK_FAULT = 0x4c420103u } lb_marker_t;
lb_boot_decision_t lb_boot_classify(uint32_t reset_causes,
                                   uint32_t backup_word, uint32_t backup_inverse);

typedef enum {
    LB_FAULT_NONE = 0, LB_FAULT_POWER_SWITCH, LB_FAULT_BACKUP_WRITE,
    LB_FAULT_ADC, LB_FAULT_ADC_STALE, LB_FAULT_DMA,
    LB_FAULT_TRANSFER_TIMEOUT, LB_FAULT_INIT, LB_FAULT_CPU
} lb_fault_t;

/* Critical sections must save/restore the previous interrupt mask. The target
 * port's FAULT ISR must call lb_guard_trip immediately; no HAL polling in ISR.
 * transfer_start receives an already encoded persistent buffer.
 */
typedef struct {
    void *context;
    uint32_t (*critical_enter)(void *context);
    void (*critical_exit)(void *context, uint32_t key);
    bool (*fault_active_or_pending)(void *context);
    void (*enable_write)(void *context, bool high);
    void (*transfer_stop_low)(void *context);
    bool (*marker_commit)(void *context, lb_marker_t marker, lb_fault_t reason);
    bool (*transfer_start)(void *context, const uint16_t *data, size_t words);
    bool (*transfer_busy)(void *context);
} lb_io_t;

typedef struct {
    lb_io_t io;
    volatile uint32_t tripped;
    volatile uint32_t enabled;
    volatile lb_fault_t fault;
} lb_guard_t;
void lb_guard_init(lb_guard_t *guard, const lb_io_t *io);
void lb_guard_trip(lb_guard_t *guard, lb_fault_t reason);
bool lb_guard_prepare_boot(lb_guard_t *guard);
bool lb_guard_enable(lb_guard_t *guard);
bool lb_guard_transfer(lb_guard_t *guard, const uint16_t *data, size_t words);

typedef enum {
    LB_STATE_RESET_LOCKOUT, LB_STATE_STABILIZE, LB_STATE_POWER_WAIT,
    LB_STATE_BLACK_FRAME, LB_STATE_ACTIVE, LB_STATE_FAULT
} lb_state_t;

typedef struct {
    lb_guard_t guard;
    lb_calibration_t calibration;
    lb_switch_t mode_switch;
    lb_state_t state;
    lb_boot_decision_t boot;
    uint32_t state_since;
    uint32_t adc_at;
    uint32_t frame_at;
    uint32_t vdda_mv;
    int32_t cv_mv;
    bool have_adc;
    lb_mode_t last_render_mode;
    lb_frame_t frame;
    uint16_t dma[LB_WS_DMA_WORDS];
} lb_controller_t;

void lb_controller_init(lb_controller_t *controller, const lb_io_t *io,
                        const lb_calibration_t *cal, lb_boot_decision_t boot,
                        uint32_t now);
bool lb_controller_adc(lb_controller_t *controller, uint16_t adc_code,
                       uint16_t vref_code, uint32_t now);
void lb_controller_step(lb_controller_t *controller, uint8_t raw_ab, uint32_t now);

#endif
