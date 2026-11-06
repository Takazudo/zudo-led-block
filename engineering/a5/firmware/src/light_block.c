#include "light_block.h"

static uint32_t elapsed(uint32_t now, uint32_t then) { return now - then; }

void lb_switch_init(lb_switch_t *sw, uint32_t now)
{
    sw->candidate = 0u;
    sw->stable = 0u;
    sw->candidate_since = now;
}

lb_mode_t lb_switch_update(lb_switch_t *sw, uint8_t ab, uint32_t now)
{
    ab &= 3u; /* bit 1 = PA2/MODE_A, bit 0 = PA3/MODE_B */
    if (ab != sw->candidate) {
        sw->candidate = ab;
        sw->candidate_since = now;
    } else if (elapsed(now, sw->candidate_since) >= LB_SWITCH_DEBOUNCE_MS) {
        sw->stable = ab;
    }
    return (lb_mode_t)sw->stable;
}

lb_calibration_t lb_calibration_default(uint16_t factory_vrefint_cal)
{
    lb_calibration_t c = {
        (int32_t)((4095ULL * 65536u * LB_ADC_DIVIDER_NUM + LB_ADC_DIVIDER_DEN) /
                  (2u * LB_ADC_DIVIDER_DEN)), 65536u, factory_vrefint_cal
    };
    return c;
}

bool lb_adc_to_cv(const lb_calibration_t *cal, uint16_t adc_code,
                  uint16_t vref_code, int32_t *cv_mv, uint32_t *vdda_mv)
{
    if (!cal || !cv_mv || !vdda_mv || adc_code > 4095u || vref_code == 0u ||
        vref_code > 4095u || cal->vrefint_cal == 0u || cal->vrefint_cal > 4095u ||
        cal->zero_code_q16 < 0 || cal->zero_code_q16 > (4095 << 16) ||
        cal->gain_q16 < 32768u || cal->gain_q16 > 131072u) {
        return false;
    }
    uint32_t supply = (3000u * cal->vrefint_cal + vref_code / 2u) / vref_code;
    if (supply < LB_VDDA_MIN_MV || supply > LB_VDDA_MAX_MV) return false;
    int64_t delta = (int64_t)adc_code * 65536 - cal->zero_code_q16;
    /* A5: VADC = (100/133)*(VDDA/2 + CV/8). Keep precision and avoid overflow.
     * Apply calibrated zero and gain, using signed integer arithmetic only. */
    int64_t millivolts_q16 = delta * (int64_t)supply * LB_ADC_INVERSE_GAIN_NUM /
                            (4095 * LB_ADC_INVERSE_GAIN_DEN);
    millivolts_q16 = millivolts_q16 * cal->gain_q16 / 65536;
    int64_t rounded = millivolts_q16 >= 0 ? millivolts_q16 + 32768 : millivolts_q16 - 32768;
    *cv_mv = (int32_t)(rounded / 65536);
    *vdda_mv = supply;
    return true;
}

void lb_frame_black(lb_frame_t *frame)
{
    for (size_t side = 0; side < LB_CHAINS; ++side)
        for (size_t i = 0; i < LB_PIXELS_PER_CHAIN; ++i)
            frame->chain[side][i] = (lb_rgb_t){ 0, 0, 0 };
}

static uint8_t capped_scale(uint8_t base, uint32_t level)
{
    uint32_t value = (uint32_t)base * level / 65535u;
    return (uint8_t)(value > LB_CHANNEL_CAP ? LB_CHANNEL_CAP : value);
}

void lb_render(lb_frame_t *frame, lb_mode_t mode, int32_t cv_mv, uint32_t now_ms)
{
    lb_frame_black(frame);
    for (size_t side = 0; side < LB_CHAINS; ++side) {
        lb_rgb_t color = { 0, 0, 0 };
        uint32_t level = 0;
        if (mode == LB_MODE_ON) {
            color = (lb_rgb_t){ LB_CHANNEL_CAP, LB_CHANNEL_CAP, LB_CHANNEL_CAP };
            level = 65535u;
        } else if (mode == LB_MODE_CV) {
            int64_t magnitude = cv_mv < 0 ? -(int64_t)cv_mv : cv_mv;
            if (magnitude > LB_CV_FULL_SCALE_MV) magnitude = LB_CV_FULL_SCALE_MV;
            if (magnitude > LB_CV_DEADBAND_MV) {
                level = (uint32_t)((magnitude - LB_CV_DEADBAND_MV) * 65535 /
                                  (LB_CV_FULL_SCALE_MV - LB_CV_DEADBAND_MV));
                color = cv_mv >= 0 ? (lb_rgb_t){ 51, 22, 4 } : (lb_rgb_t){ 4, 22, 51 };
            }
        } else if (mode == LB_MODE_PROGRAM) {
            /* Provisional 8-second triangular breath; independent opposite phases. */
            uint32_t phase = (now_ms % LB_PROGRAM_PERIOD_MS +
                              (uint32_t)side * (LB_PROGRAM_PERIOD_MS / 2u)) % LB_PROGRAM_PERIOD_MS;
            uint32_t ramp = phase <= LB_PROGRAM_PERIOD_MS / 2u ? phase : LB_PROGRAM_PERIOD_MS - phase;
            level = ramp * 65535u / (LB_PROGRAM_PERIOD_MS / 2u);
            color = side == 0 ? (lb_rgb_t){ 51, 18, 6 } : (lb_rgb_t){ 6, 18, 51 };
        }
        lb_rgb_t pixel = { capped_scale(color.r, level), capped_scale(color.g, level),
                           capped_scale(color.b, level) };
        for (size_t i = 0; i < LB_PIXELS_PER_CHAIN; ++i) frame->chain[side][i] = pixel;
    }
}

bool lb_ws_encode(const lb_frame_t *frame, uint16_t *interleaved, size_t capacity_words)
{
    if (!frame || !interleaved || capacity_words < LB_WS_DMA_WORDS) return false;
    for (size_t n = 0; n < LB_WS_DMA_WORDS; ++n) interleaved[n] = 0u;
    for (size_t side = 0; side < LB_CHAINS; ++side) {
        for (size_t p = 0; p < LB_PIXELS_PER_CHAIN; ++p) {
            lb_rgb_t pixel = frame->chain[side][p];
            /* Defense in depth: callers cannot bypass the initial 20% cap. */
            uint8_t grb[3] = {
                pixel.g > LB_CHANNEL_CAP ? LB_CHANNEL_CAP : pixel.g,
                pixel.r > LB_CHANNEL_CAP ? LB_CHANNEL_CAP : pixel.r,
                pixel.b > LB_CHANNEL_CAP ? LB_CHANNEL_CAP : pixel.b
            };
            for (size_t c = 0; c < 3u; ++c) {
                for (size_t b = 0; b < 8u; ++b) {
                    size_t slot = LB_WS_LEADING_SLOTS + p * 24u + c * 8u + b;
                    interleaved[slot * LB_CHAINS + side] =
                        (grb[c] & (uint8_t)(0x80u >> b)) != 0u ?
                        LB_WS_ONE_HIGH_TICKS : LB_WS_ZERO_HIGH_TICKS;
                }
            }
        }
    }
    return true;
}

lb_boot_decision_t lb_boot_classify(uint32_t reset_causes, uint32_t word, uint32_t inverse)
{
    const uint32_t unsafe_causes = LB_RESET_SOFTWARE | LB_RESET_IWDG | LB_RESET_WWDG |
                                    LB_RESET_OPTION | LB_RESET_LOWPOWER;
    if ((reset_causes & LB_RESET_POWER) == 0u || (reset_causes & unsafe_causes) != 0u)
        return LB_BOOT_LOCKED_RESET_CAUSE;
    /* PINRSTF is also raised by power/system resets on this MCU; it is not a veto.
     * PWRRSTF combines BOR with POR/PDR. Only a reset backup pair is a candidate
     * for normal startup; it does NOT prove a deliberate human power cycle. */
    if (word == 0u && inverse == 0u) return LB_BOOT_COLD_CANDIDATE;
    if (inverse == ~word && (word == LB_MARK_BOOT || word == LB_MARK_ARMED || word == LB_MARK_FAULT))
        return LB_BOOT_LOCKED_RETAINED;
    return LB_BOOT_LOCKED_CORRUPT;
}

void lb_guard_init(lb_guard_t *guard, const lb_io_t *io)
{
    guard->io = *io;
    guard->tripped = 0u;
    guard->enabled = 0u;
    guard->fault = LB_FAULT_NONE;
    io->enable_write(io->context, false);
    io->transfer_stop_low(io->context);
}

void lb_guard_trip(lb_guard_t *guard, lb_fault_t reason)
{
    /* No enable or retry path exists in this routine. May be called from ISR. */
    guard->tripped = 1u;
    guard->enabled = 0u;
    guard->io.enable_write(guard->io.context, false);
    guard->io.transfer_stop_low(guard->io.context);
    if (guard->fault == LB_FAULT_NONE) guard->fault = reason;
    (void)guard->io.marker_commit(guard->io.context, LB_MARK_FAULT, guard->fault);
}

static bool guard_bad(lb_guard_t *guard)
{
    return guard->tripped != 0u || guard->io.fault_active_or_pending(guard->io.context);
}

bool lb_guard_prepare_boot(lb_guard_t *guard)
{
    uint32_t key = guard->io.critical_enter(guard->io.context);
    bool ok = !guard_bad(guard);
    if (ok) ok = guard->io.marker_commit(guard->io.context, LB_MARK_BOOT, LB_FAULT_NONE);
    if (!ok) lb_guard_trip(guard, guard_bad(guard) ? LB_FAULT_POWER_SWITCH : LB_FAULT_BACKUP_WRITE);
    guard->io.critical_exit(guard->io.context, key);
    return ok && guard->tripped == 0u;
}

bool lb_guard_enable(lb_guard_t *guard)
{
    uint32_t key = guard->io.critical_enter(guard->io.context);
    if (guard_bad(guard)) {
        lb_guard_trip(guard, LB_FAULT_POWER_SWITCH);
    } else if (!guard->io.marker_commit(guard->io.context, LB_MARK_ARMED, LB_FAULT_NONE)) {
        lb_guard_trip(guard, LB_FAULT_BACKUP_WRITE);
    } else if (guard_bad(guard)) {
        lb_guard_trip(guard, LB_FAULT_POWER_SWITCH);
    } else {
        guard->enabled = 1u;
        guard->io.enable_write(guard->io.context, true); /* HIGH -> NPN -> /EN LOW */
        if (guard_bad(guard)) lb_guard_trip(guard, LB_FAULT_POWER_SWITCH);
    }
    guard->io.critical_exit(guard->io.context, key);
    /* A pending FAULT IRQ may execute at critical_exit, before this return. */
    return guard->enabled != 0u && guard->tripped == 0u;
}

bool lb_guard_transfer(lb_guard_t *guard, const uint16_t *data, size_t words)
{
    uint32_t key = guard->io.critical_enter(guard->io.context);
    bool started = false;
    if (guard_bad(guard)) {
        lb_guard_trip(guard, LB_FAULT_POWER_SWITCH);
    } else if (guard->enabled != 0u) {
        started = guard->io.transfer_start(guard->io.context, data, words);
        if (!started) lb_guard_trip(guard, LB_FAULT_DMA);
        else if (guard_bad(guard)) lb_guard_trip(guard, LB_FAULT_POWER_SWITCH);
    }
    guard->io.critical_exit(guard->io.context, key);
    return started && guard->tripped == 0u && guard->enabled != 0u;
}

void lb_controller_init(lb_controller_t *c, const lb_io_t *io,
                        const lb_calibration_t *cal, lb_boot_decision_t boot, uint32_t now)
{
    /* Explicit initialization keeps the host and freestanding builds identical. */
    c->calibration = *cal;
    c->boot = boot;
    c->state_since = now;
    c->adc_at = now;
    c->frame_at = now;
    c->vdda_mv = 0;
    c->cv_mv = 0;
    c->have_adc = false;
    c->last_render_mode = LB_MODE_INVALID;
    c->state = boot == LB_BOOT_COLD_CANDIDATE ? LB_STATE_STABILIZE : LB_STATE_RESET_LOCKOUT;
    lb_switch_init(&c->mode_switch, now);
    lb_frame_black(&c->frame);
    lb_guard_init(&c->guard, io);
    if (c->state == LB_STATE_STABILIZE && !lb_guard_prepare_boot(&c->guard)) c->state = LB_STATE_FAULT;
}

bool lb_controller_adc(lb_controller_t *c, uint16_t adc_code, uint16_t vref_code, uint32_t now)
{
    int32_t sample;
    uint32_t supply;
    if (!lb_adc_to_cv(&c->calibration, adc_code, vref_code, &sample, &supply)) {
        lb_guard_trip(&c->guard, LB_FAULT_ADC);
        c->state = LB_STATE_FAULT;
        return false;
    }
    c->cv_mv = c->have_adc ? c->cv_mv + (sample - c->cv_mv) / 8 : sample;
    c->vdda_mv = supply;
    c->adc_at = now;
    c->have_adc = true;
    return true;
}

static bool controller_send(lb_controller_t *c, uint32_t now)
{
    if (!lb_ws_encode(&c->frame, c->dma, LB_WS_DMA_WORDS)) {
        lb_guard_trip(&c->guard, LB_FAULT_DMA);
        c->state = LB_STATE_FAULT;
        return false;
    }
    if (!lb_guard_transfer(&c->guard, c->dma, LB_WS_DMA_WORDS)) {
        c->state = LB_STATE_FAULT;
        return false;
    }
    c->frame_at = now;
    return true;
}

void lb_controller_step(lb_controller_t *c, uint8_t raw_ab, uint32_t now)
{
    lb_mode_t mode = lb_switch_update(&c->mode_switch, raw_ab, now);
    /* An observed impossible switch contact combination blanks immediately;
     * other contact transitions retain the debounced mode for 20 ms. */
    if ((raw_ab & 3u) == 0u) mode = LB_MODE_INVALID;
    if (c->guard.io.fault_active_or_pending(c->guard.io.context)) lb_guard_trip(&c->guard, LB_FAULT_POWER_SWITCH);
    if (c->guard.tripped != 0u) c->state = LB_STATE_FAULT;
    if (c->state == LB_STATE_FAULT || c->state == LB_STATE_RESET_LOCKOUT) return;

    bool fresh_adc = c->have_adc && elapsed(now, c->adc_at) <= LB_ADC_MAX_AGE_MS;
    if (c->state == LB_STATE_STABILIZE) {
        if (!fresh_adc) {
            if (elapsed(now, c->state_since) > LB_STARTUP_ADC_TIMEOUT_MS) {
                lb_guard_trip(&c->guard, LB_FAULT_ADC_STALE);
                c->state = LB_STATE_FAULT;
            }
            return;
        }
        if (elapsed(now, c->state_since) >= LB_STARTUP_SETTLE_MS && mode != LB_MODE_INVALID) {
            if (lb_guard_enable(&c->guard)) {
                c->state = LB_STATE_POWER_WAIT;
                c->state_since = now;
            } else c->state = LB_STATE_FAULT;
        }
        return;
    }
    if (!fresh_adc) {
        lb_guard_trip(&c->guard, LB_FAULT_ADC_STALE);
        c->state = LB_STATE_FAULT;
        return;
    }
    if (c->state == LB_STATE_POWER_WAIT) {
        if (elapsed(now, c->state_since) >= LB_LED_POWER_SETTLE_MS) {
            lb_frame_black(&c->frame);
            if (controller_send(c, now)) c->state = LB_STATE_BLACK_FRAME;
        }
        return;
    }
    bool busy = c->guard.io.transfer_busy(c->guard.io.context);
    if (busy && elapsed(now, c->frame_at) > LB_TRANSFER_TIMEOUT_MS) {
        lb_guard_trip(&c->guard, LB_FAULT_TRANSFER_TIMEOUT);
        c->state = LB_STATE_FAULT;
        return;
    }
    if (c->state == LB_STATE_BLACK_FRAME) {
        if (!busy) { c->state = LB_STATE_ACTIVE; c->frame_at = now - LB_FRAME_INTERVAL_MS; }
        else return;
    }
    if (!busy && (mode != c->last_render_mode || elapsed(now, c->frame_at) >= LB_FRAME_INTERVAL_MS)) {
        lb_render(&c->frame, mode, c->cv_mv, now);
        if (controller_send(c, now)) c->last_render_mode = mode;
    }
}
