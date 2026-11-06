#include "light_block.h"
#include <assert.h>
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

static unsigned checks;
#define CHECK(expression) do { ++checks; if (!(expression)) { \
    fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #expression); \
    assert(expression); } } while (0)

typedef enum { INJECT_NONE, INJECT_ARM_MARKER, INJECT_ENABLE,
               INJECT_POSTCHECK, INJECT_EXIT, INJECT_TRANSFER } inject_t;
typedef struct {
    lb_guard_t *guard;
    bool enabled, busy, level_low, edge_pending;
    bool marker_fail, transfer_fail, masked;
    uint32_t marker, inverse, reason;
    unsigned enable_rises, enable_lows, transfers, stops, fault_checks;
    inject_t injection;
    uint16_t last_dma[LB_WS_DMA_WORDS];
} fake_t;

static uint32_t fake_enter(void *v)
{
    fake_t *f = v;
    uint32_t old = f->masked ? 1u : 0u;
    f->masked = true;
    return old;
}
static void fake_irq(fake_t *f)
{
    if (!f->masked && f->edge_pending && f->guard) {
        lb_guard_trip(f->guard, LB_FAULT_POWER_SWITCH);
        f->edge_pending = false;
    }
}
static void fake_exit(void *v, uint32_t key)
{
    fake_t *f = v;
    if (f->injection == INJECT_EXIT) { f->edge_pending = true; f->injection = INJECT_NONE; }
    f->masked = key != 0;
    fake_irq(f);
}
static bool fake_fault(void *v)
{
    fake_t *f = v;
    ++f->fault_checks;
    bool value = f->level_low || f->edge_pending;
    if (f->injection == INJECT_POSTCHECK && f->enabled) {
        f->edge_pending = true; /* edge immediately AFTER the last input read */
        f->injection = INJECT_NONE;
    }
    return value;
}
static void fake_enable(void *v, bool high)
{
    fake_t *f = v;
    if (high) {
        /* The real guard must commit the armed marker before the GPIO rises. */
        CHECK(f->marker == LB_MARK_ARMED && f->inverse == ~(uint32_t)LB_MARK_ARMED);
        CHECK(f->masked);
        CHECK(!f->guard->tripped);
        ++f->enable_rises;
        if (f->injection == INJECT_ENABLE) { f->edge_pending = true; f->injection = INJECT_NONE; }
    } else ++f->enable_lows;
    f->enabled = high;
}
static void fake_stop(void *v) { fake_t *f = v; f->busy = false; ++f->stops; }
static bool fake_marker(void *v, lb_marker_t marker, lb_fault_t reason)
{
    fake_t *f = v;
    f->marker = (uint32_t)marker;
    if (f->marker_fail) return false; /* intentionally torn write */
    f->inverse = ~(uint32_t)marker;
    f->reason = (uint32_t)reason;
    if (marker == LB_MARK_ARMED && f->injection == INJECT_ARM_MARKER) {
        f->edge_pending = true; f->injection = INJECT_NONE;
    }
    return true;
}
static bool fake_start(void *v, const uint16_t *data, size_t words)
{
    fake_t *f = v;
    CHECK(f->masked && f->enabled && !f->guard->tripped);
    CHECK(words == LB_WS_DMA_WORDS);
    if (f->transfer_fail || f->busy) return false;
    memcpy(f->last_dma, data, sizeof f->last_dma);
    f->busy = true;
    ++f->transfers;
    if (f->injection == INJECT_TRANSFER) { f->edge_pending = true; f->injection = INJECT_NONE; }
    return true;
}
static bool fake_busy(void *v) { return ((fake_t *)v)->busy; }
static lb_io_t fake_io(fake_t *f)
{
    lb_io_t io = { f, fake_enter, fake_exit, fake_fault, fake_enable, fake_stop,
                   fake_marker, fake_start, fake_busy };
    return io;
}
static void guard_setup(fake_t *f, lb_guard_t *g)
{
    memset(f, 0, sizeof *f);
    f->guard = g;
    lb_io_t io = fake_io(f);
    lb_guard_init(g, &io);
}
static void controller_setup(fake_t *f, lb_controller_t *c, lb_boot_decision_t boot, uint32_t now)
{
    memset(f, 0, sizeof *f);
    f->guard = &c->guard;
    lb_io_t io = fake_io(f);
    lb_calibration_t cal = lb_calibration_default(1500u);
    lb_controller_init(c, &io, &cal, boot, now);
}

/* Independent forward oracle, from actual A5 resistor values rather than the
 * firmware inverse constants. R24=330, R25=1000, front-end affine gain1/8. */
static uint16_t cv_code(int32_t cv_mv, uint32_t vdda_mv)
{
    double voltage = ((double)vdda_mv / 2.0 + (double)cv_mv / 8.0) * 1000.0 / 1330.0;
    double code = voltage / (double)vdda_mv * 4095.0;
    if (code < 0.0) code = 0.0;
    if (code > 4095.0) code = 4095.0;
    return (uint16_t)(code + 0.5);
}
static void sample_at(lb_controller_t *c, uint32_t now, int32_t cv_mv)
{
    CHECK(lb_controller_adc(c, cv_code(cv_mv, 3300), 1364, now));
}
static void run_to_active(fake_t *f, lb_controller_t *c, uint8_t mode, uint32_t start)
{
    for (uint32_t n = 0; n <= 110u; ++n) {
        uint32_t now = start + n;
        f->busy = false; /* model successful completion well before the next1ms tick */
        sample_at(c, now, 0);
        lb_controller_step(c, mode, now);
        if (n < LB_STARTUP_SETTLE_MS) CHECK(!f->enabled);
    }
    CHECK(c->state == LB_STATE_ACTIVE);
    CHECK(f->enabled && f->enable_rises == 1u);
}

static void test_switch(void)
{
    lb_switch_t sw;
    lb_switch_init(&sw, 0);
    CHECK(lb_switch_update(&sw, 1, 0) == LB_MODE_INVALID);
    CHECK(lb_switch_update(&sw, 1, 19) == LB_MODE_INVALID);
    CHECK(lb_switch_update(&sw, 1, 20) == LB_MODE_ON);
    CHECK(lb_switch_update(&sw, 3, 21) == LB_MODE_ON);
    CHECK(lb_switch_update(&sw, 2, 25) == LB_MODE_ON);
    CHECK(lb_switch_update(&sw, 3, 30) == LB_MODE_ON);
    CHECK(lb_switch_update(&sw, 3, 50) == LB_MODE_PROGRAM);
    CHECK(lb_switch_update(&sw, 2, 51) == LB_MODE_PROGRAM);
    CHECK(lb_switch_update(&sw, 2, 71) == LB_MODE_CV);
    CHECK(lb_switch_update(&sw, 0, 72) == LB_MODE_CV);
    CHECK(lb_switch_update(&sw, 0, 92) == LB_MODE_INVALID);
    lb_switch_init(&sw, UINT32_MAX - 10u);
    CHECK(lb_switch_update(&sw, 1, UINT32_MAX - 10u) == LB_MODE_INVALID);
    CHECK(lb_switch_update(&sw, 1, 9u) == LB_MODE_ON); /* unsigned20ms wrap */
}

static void test_adc(void)
{
    lb_calibration_t c = lb_calibration_default(1500);
    const uint32_t supplies[] = {3000, 3300, 3600};
    const int32_t inputs[] = {-5000, -2500, 0, 2500, 5000};
    for (size_t v = 0; v < 3; ++v) {
        uint16_t ref = (uint16_t)((4500000u + supplies[v]/2u) / supplies[v]);
        for (size_t n = 0; n < 5; ++n) {
            int32_t mv; uint32_t supply;
            CHECK(lb_adc_to_cv(&c, cv_code(inputs[n], supplies[v]), ref, &mv, &supply));
            CHECK(mv >= inputs[n]-10 && mv <= inputs[n]+10);
            CHECK(supply >= supplies[v]-1u && supply <= supplies[v]+1u);
        }
    }
    int32_t mv; uint32_t supply;
    CHECK(!lb_adc_to_cv(&c, 1000, 0, &mv, &supply));
    CHECK(!lb_adc_to_cv(&c, 4096, 1500, &mv, &supply));
    CHECK(!lb_adc_to_cv(&c, 1000, 100, &mv, &supply));
    CHECK(!lb_adc_to_cv(NULL, 1000, 1500, &mv, &supply));
    c.vrefint_cal = 0xffff;
    CHECK(!lb_adc_to_cv(&c, 1000, 1500, &mv, &supply));
    c = lb_calibration_default(1500);
    c.zero_code_q16 = (int32_t)cv_code(0, 3300) * 65536;
    CHECK(lb_adc_to_cv(&c, cv_code(0, 3300), 1364, &mv, &supply) && mv == 0);
    c.gain_q16 = 72090u; /* measured gain correction example, not factory setting */
    CHECK(lb_adc_to_cv(&c, cv_code(5000, 3300), 1364, &mv, &supply));
    CHECK(mv >= 5485 && mv <= 5515);
    c.gain_q16 = 0;
    CHECK(!lb_adc_to_cv(&c, 1000, 1500, &mv, &supply));
}

static uint32_t random_word(uint32_t *seed)
{
    *seed ^= *seed << 13; *seed ^= *seed >> 17; *seed ^= *seed << 5;
    return *seed;
}
static void frame_capped(const lb_frame_t *frame)
{
    for (size_t s=0; s<LB_CHAINS; ++s) for (size_t p=0; p<LB_PIXELS_PER_CHAIN; ++p) {
        CHECK(frame->chain[s][p].r <= 51);
        CHECK(frame->chain[s][p].g <= 51);
        CHECK(frame->chain[s][p].b <= 51);
    }
}
static void test_render(void)
{
    lb_frame_t frame;
    lb_render(&frame, LB_MODE_ON, 0, 0);
    CHECK(frame.chain[0][0].r == 51 && frame.chain[1][3].b == 51);
    lb_render(&frame, LB_MODE_CV, 0, 0);
    CHECK(frame.chain[0][0].r == 0 && frame.chain[1][3].b == 0);
    lb_render(&frame, LB_MODE_CV, 50, 0);
    CHECK(frame.chain[0][0].r == 0);
    lb_render(&frame, LB_MODE_CV, 5000, 0);
    CHECK(frame.chain[0][0].r == 51 && frame.chain[0][0].b == 4);
    lb_render(&frame, LB_MODE_CV, -5000, 0);
    CHECK(frame.chain[0][0].r == 4 && frame.chain[0][0].b == 51);
    lb_render(&frame, LB_MODE_CV, INT32_MIN, UINT32_MAX);
    frame_capped(&frame);
    lb_render(&frame, LB_MODE_PROGRAM, 0, 0);
    CHECK(frame.chain[0][0].r == 0 && frame.chain[1][0].b == 51);
    uint32_t seed = 0xA5031u;
    for (unsigned n=0; n<10000; ++n) {
        uint32_t word = random_word(&seed);
        lb_render(&frame, (lb_mode_t)(word & 3u), (int32_t)random_word(&seed), random_word(&seed));
        frame_capped(&frame);
    }
}

static void test_ws2812(void)
{
    lb_frame_t frame;
    lb_frame_black(&frame);
    frame.chain[0][0] = (lb_rgb_t){ 1, 2, 3 };
    frame.chain[1][0] = (lb_rgb_t){ 4, 8, 16 };
    frame.chain[0][3] = (lb_rgb_t){ 255, 255, 255 }; /* encoder cap cannot be bypassed */
    uint16_t buffer[LB_WS_DMA_WORDS + 2u];
    for (size_t n=0; n<LB_WS_DMA_WORDS+2u; ++n) buffer[n] = 0xdead;
    CHECK(!lb_ws_encode(&frame, buffer, LB_WS_DMA_WORDS-1));
    CHECK(buffer[0] == 0xdead);
    CHECK(lb_ws_encode(&frame, buffer, LB_WS_DMA_WORDS));
    CHECK(buffer[LB_WS_DMA_WORDS] == 0xdead && buffer[LB_WS_DMA_WORDS+1] == 0xdead);
    for (size_t side=0; side<2; ++side) {
        for (size_t p=0; p<4; ++p) {
            uint8_t decoded[3] = {0};
            for (size_t component=0; component<3; ++component) {
                for (size_t bit=0; bit<8; ++bit) {
                    size_t slot=LB_WS_LEADING_SLOTS+p*24+component*8+bit;
                    uint16_t high=buffer[slot*2+side];
                    CHECK(high==LB_WS_ZERO_HIGH_TICKS || high==LB_WS_ONE_HIGH_TICKS);
                    decoded[component]=(uint8_t)((decoded[component]<<1) | (high==LB_WS_ONE_HIGH_TICKS ? 1u : 0u));
                }
            }
            lb_rgb_t pixel = frame.chain[side][p];
            CHECK(decoded[0] == (pixel.g>51 ? 51 : pixel.g));
            CHECK(decoded[1] == (pixel.r>51 ? 51 : pixel.r));
            CHECK(decoded[2] == (pixel.b>51 ? 51 : pixel.b));
        }
    }
    for (size_t slot=0; slot<LB_WS_SLOTS; ++slot) {
        if (slot<LB_WS_LEADING_SLOTS || slot>=LB_WS_LEADING_SLOTS+LB_WS_BITS)
            CHECK(buffer[slot*2]==0 && buffer[slot*2+1]==0);
    }
    /* Independent PWM+preload model: an update makes the previous preload
     * active, then the two DMA halfword writes fill the following preload.
     * DMA completion stops before that newly active cell can finish. */
    uint16_t preload[2]={0}, active[2]={0};
    unsigned complete_tail=0;
    for (size_t update=0; update<LB_WS_SLOTS; ++update) {
        active[0]=preload[0]; active[1]=preload[1];
        preload[0]=buffer[update*2]; preload[1]=buffer[update*2+1];
        if (update+1u==LB_WS_SLOTS) break;
        if (update>=LB_WS_LEADING_SLOTS+LB_WS_BITS+1u) {
            CHECK(active[0]==0 && active[1]==0);
            ++complete_tail;
        }
    }
    CHECK(complete_tail == LB_WS_RESET_SLOTS-2u);
    for (int ppm=-30000; ppm<=30000; ++ppm) {
        double hz=(double)LB_TIMER_CLOCK_HZ*(1.0+(double)ppm/1000000.0);
        double zero_high=LB_WS_ZERO_HIGH_TICKS*1e9/hz;
        double one_high=LB_WS_ONE_HIGH_TICKS*1e9/hz;
        double zero_low=(LB_WS_PERIOD_TICKS-LB_WS_ZERO_HIGH_TICKS)*1e9/hz;
        double one_low=(LB_WS_PERIOD_TICKS-LB_WS_ONE_HIGH_TICKS)*1e9/hz;
        CHECK(zero_high>=220.0 && zero_high<=380.0);
        CHECK(zero_low>=580.0 && zero_low<=1000.0);
        CHECK(one_high>=580.0 && one_high<=1000.0);
        CHECK(one_low>=220.0 && one_low<=420.0);
        CHECK(LB_WS_PERIOD_TICKS*1e9/hz >= 1250.0);
        CHECK(complete_tail*LB_WS_PERIOD_TICKS*1e6/hz >= 280.0);
        CHECK(hz<=64000000.0);
    }
}

static void test_reset_policy(void)
{
    CHECK(lb_boot_classify(LB_RESET_POWER|LB_RESET_PIN, 0, 0)==LB_BOOT_COLD_CANDIDATE);
    CHECK(lb_boot_classify(0, 0, 0)==LB_BOOT_LOCKED_RESET_CAUSE);
    CHECK(lb_boot_classify(LB_RESET_PIN, 0, 0)==LB_BOOT_LOCKED_RESET_CAUSE);
    const uint32_t bad[]={LB_RESET_SOFTWARE,LB_RESET_IWDG,LB_RESET_WWDG,LB_RESET_OPTION,LB_RESET_LOWPOWER};
    for (size_t i=0; i<sizeof bad/sizeof bad[0]; ++i)
        CHECK(lb_boot_classify(LB_RESET_POWER|LB_RESET_PIN|bad[i],0,0)==LB_BOOT_LOCKED_RESET_CAUSE);
    const uint32_t markers[]={LB_MARK_BOOT,LB_MARK_ARMED,LB_MARK_FAULT};
    for(size_t i=0;i<3;++i) {
        CHECK(lb_boot_classify(LB_RESET_POWER,markers[i],~markers[i])==LB_BOOT_LOCKED_RETAINED);
        CHECK(lb_boot_classify(LB_RESET_POWER,markers[i],0)==LB_BOOT_LOCKED_CORRUPT);
        for(unsigned bit=0;bit<32;++bit)
            CHECK(lb_boot_classify(LB_RESET_POWER,markers[i]^(1u<<bit),~markers[i])==LB_BOOT_LOCKED_CORRUPT);
    }
    CHECK(lb_boot_classify(LB_RESET_POWER,0,UINT32_MAX)==LB_BOOT_LOCKED_CORRUPT);
    /* Full supply collapse erases both words and is intentionally identical to
     * unplug/replug. This tested limitation must remain visible in the docs. */
    CHECK(lb_boot_classify(LB_RESET_POWER,0,0)==LB_BOOT_COLD_CANDIDATE);
    fake_t f; lb_controller_t c;
    const lb_boot_decision_t locked[]={LB_BOOT_LOCKED_RESET_CAUSE,LB_BOOT_LOCKED_RETAINED,LB_BOOT_LOCKED_CORRUPT};
    for(size_t k=0;k<3;++k) for(uint8_t mode=1;mode<4;++mode) {
        controller_setup(&f,&c,locked[k],0);
        for(uint32_t t=0;t<1000;++t) { sample_at(&c,t,5000); lb_controller_step(&c,mode,t); }
        CHECK(c.state==LB_STATE_RESET_LOCKOUT && !f.enabled && !f.busy && f.enable_rises==0);
    }
}

static void test_guard_races(void)
{
    fake_t f; lb_guard_t guard;
    uint16_t buffer[LB_WS_DMA_WORDS]={0};
    guard_setup(&f,&guard);
    f.level_low=true;
    CHECK(!lb_guard_enable(&guard));
    CHECK(f.enable_rises==0 && !f.enabled && guard.tripped);
    const inject_t races[]={INJECT_ARM_MARKER,INJECT_ENABLE,INJECT_POSTCHECK,INJECT_EXIT};
    for(size_t i=0;i<sizeof races/sizeof races[0];++i) {
        guard_setup(&f,&guard); f.injection=races[i];
        CHECK(!lb_guard_enable(&guard));
        CHECK(!f.enabled && !f.busy && guard.tripped);
        CHECK(f.marker==LB_MARK_FAULT);
        unsigned rises=f.enable_rises;
        f.level_low=false; f.edge_pending=false; /* TPS /FAULT deasserts when disabled */
        for(unsigned retry=0;retry<100;++retry) CHECK(!lb_guard_enable(&guard));
        CHECK(f.enable_rises==rises && !f.enabled);
    }
    guard_setup(&f,&guard); f.marker_fail=true;
    CHECK(!lb_guard_enable(&guard));
    CHECK(f.enable_rises==0 && guard.fault==LB_FAULT_BACKUP_WRITE);
    CHECK(lb_boot_classify(LB_RESET_POWER,f.marker,f.inverse)!=LB_BOOT_COLD_CANDIDATE);
    guard_setup(&f,&guard);
    CHECK(lb_guard_prepare_boot(&guard));
    CHECK(f.marker==LB_MARK_BOOT && f.enable_rises==0);
    CHECK(lb_guard_enable(&guard));
    f.injection=INJECT_TRANSFER;
    CHECK(!lb_guard_transfer(&guard,buffer,LB_WS_DMA_WORDS));
    CHECK(!f.enabled && !f.busy && guard.tripped);
    guard_setup(&f,&guard);
    CHECK(lb_guard_enable(&guard));
    CHECK(lb_guard_transfer(&guard,buffer,LB_WS_DMA_WORDS));
    f.edge_pending=true; fake_irq(&f); /* active DMA abort */
    CHECK(!f.enabled && !f.busy && guard.tripped);
    f.busy=false; /* a late completion cannot re-enable anything */
    CHECK(!lb_guard_transfer(&guard,buffer,LB_WS_DMA_WORDS));
    CHECK(!f.enabled && !f.busy);
    guard_setup(&f,&guard); CHECK(lb_guard_enable(&guard)); f.transfer_fail=true;
    CHECK(!lb_guard_transfer(&guard,buffer,LB_WS_DMA_WORDS));
    CHECK(guard.fault==LB_FAULT_DMA && !f.enabled);
}

static void test_controller(void)
{
    fake_t f; lb_controller_t c;
    controller_setup(&f,&c,LB_BOOT_COLD_CANDIDATE,0);
    for(uint32_t t=0;t<=LB_STARTUP_SETTLE_MS+LB_LED_POWER_SETTLE_MS;++t) {
        sample_at(&c,t,0); lb_controller_step(&c,1,t);
    }
    CHECK(c.state==LB_STATE_BLACK_FRAME && f.transfers==1);
    for(size_t slot=LB_WS_LEADING_SLOTS;slot<LB_WS_LEADING_SLOTS+LB_WS_BITS;++slot)
        CHECK(f.last_dma[slot*2]==LB_WS_ZERO_HIGH_TICKS && f.last_dma[slot*2+1]==LB_WS_ZERO_HIGH_TICKS);
    f.busy=false; sample_at(&c,106,0); lb_controller_step(&c,1,106);
    CHECK(c.state==LB_STATE_ACTIVE && c.frame.chain[0][0].r==51);
    f.busy=false; sample_at(&c,107,0); lb_controller_step(&c,0,107);
    CHECK(c.frame.chain[0][0].r==0 && f.enabled); /* invalid contact blanks, no EN cycling */
    f.busy=false; sample_at(&c,108,0); lb_controller_step(&c,1,108);
    CHECK(f.enable_rises==1);
    f.edge_pending=true; fake_irq(&f);
    CHECK(!f.enabled && !f.busy);
    unsigned rises=f.enable_rises;
    for(uint32_t t=109;t<10000;++t) {
        sample_at(&c,t,5000); lb_controller_step(&c,(uint8_t)(t&3u),t);
        CHECK(!f.enabled && !f.busy);
    }
    CHECK(f.enable_rises==rises && c.state==LB_STATE_FAULT);

    controller_setup(&f,&c,LB_BOOT_COLD_CANDIDATE,0);
    run_to_active(&f,&c,3,0);
    f.busy=false; lb_controller_step(&c,3,132);
    CHECK(c.guard.fault==LB_FAULT_ADC_STALE && !f.enabled);

    controller_setup(&f,&c,LB_BOOT_COLD_CANDIDATE,0);
    run_to_active(&f,&c,2,0);
    CHECK(!lb_controller_adc(&c,1000,0,111));
    CHECK(c.guard.fault==LB_FAULT_ADC && !f.enabled);

    controller_setup(&f,&c,LB_BOOT_COLD_CANDIDATE,0);
    run_to_active(&f,&c,1,0);
    f.busy=false; sample_at(&c,126,0); lb_controller_step(&c,1,126);
    CHECK(f.busy);
    sample_at(&c,132,0); lb_controller_step(&c,1,132);
    CHECK(c.guard.fault==LB_FAULT_TRANSFER_TIMEOUT && !f.enabled && !f.busy);

    controller_setup(&f,&c,LB_BOOT_COLD_CANDIDATE,UINT32_MAX-80u);
    run_to_active(&f,&c,1,UINT32_MAX-80u);

    controller_setup(&f,&c,LB_BOOT_COLD_CANDIDATE,0);
    for(uint32_t t=0;t<=251;++t) lb_controller_step(&c,1,t);
    CHECK(c.guard.fault==LB_FAULT_ADC_STALE && f.enable_rises==0);

    /* Deterministic random event sequences check the invariant after a trip,
     * including switch bounce, contact invalidity, fault clearing and wraps. */
    uint32_t seed=0xBADF005u;
    for(unsigned run=0;run<250;++run) {
        controller_setup(&f,&c,LB_BOOT_COLD_CANDIDATE,UINT32_MAX-200u);
        run_to_active(&f,&c,(uint8_t)(1u+run%3u),UINT32_MAX-200u);
        bool latched=false;
        for(uint32_t dt=111u;dt<600;++dt) {
            uint32_t now=UINT32_MAX-200u+dt;
            uint32_t event=random_word(&seed);
            if((event&63u)==0u) { f.edge_pending=true; fake_irq(&f); latched=true; }
            if((event&7u)==0u) f.level_low=false;
            f.busy=false;
            sample_at(&c,now,(int32_t)(event%10001u)-5000);
            lb_controller_step(&c,(uint8_t)((event>>16)&3u),now);
            if(latched) CHECK(!f.enabled && !f.busy && c.guard.tripped);
        }
    }
}

int main(void)
{
    test_switch(); puts("PASS switch truth table, bounce, invalid state, time wrap");
    test_adc(); puts("PASS A5 ADC inverse, VREFINT compensation, calibration and invalid samples");
    test_render(); puts("PASS provisional modes, CV polarity/deadband, caps and independent PROGRAM phases");
    test_ws2812(); puts("PASS two-channel GRB wire data, bounded DMA buffer, preload model and +/-3% timing sweep");
    test_reset_policy(); puts("PASS cold-domain startup, warm/BOR retention, partial markers and full-loss limitation");
    test_guard_races(); puts("PASS fault races before/during/after enable, DMA abort and no automatic retry");
    test_controller(); puts("PASS black-first startup, invalid-mode blanking, stale ADC, stuck DMA and randomized fault invariants");
    printf("PASS total assertions: %u\n",checks);
    return 0;
}
