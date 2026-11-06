#ifndef LB_CONFIG_H
#define LB_CONFIG_H

/* A5 engineering defaults. Palette, animation and CV response are provisional. */
#define LB_CHAINS                    2u
#define LB_PIXELS_PER_CHAIN          4u
#define LB_CHANNEL_CAP               51u /* floor(255 * 20 / 100), every channel */
#define LB_SWITCH_DEBOUNCE_MS        20u
#define LB_STARTUP_SETTLE_MS          100u
#define LB_STARTUP_ADC_TIMEOUT_MS    250u
#define LB_LED_POWER_SETTLE_MS       5u
#define LB_ADC_MAX_AGE_MS            20u
#define LB_FRAME_INTERVAL_MS         16u
#define LB_TRANSFER_TIMEOUT_MS       5u
#define LB_CV_FULL_SCALE_MV          5000
#define LB_CV_DEADBAND_MV            50
#define LB_VDDA_MIN_MV               3000u
#define LB_VDDA_MAX_MV               3600u
#define LB_PROGRAM_PERIOD_MS        8000u
/* A5 board: U7 follower, R24=330 ohm, R25=1 kohm at ADC.
 * VADC=(100/133)*(VDDA/2+CV/8). This binary is NOT for the unbuffered A4.1 ADC net. */
#define LB_ADC_BOARD_REVISION        5u
#define LB_ADC_DIVIDER_NUM           100u
#define LB_ADC_DIVIDER_DEN           133u
#define LB_ADC_INVERSE_GAIN_NUM      266u
#define LB_ADC_INVERSE_GAIN_DEN      25u

/* HSI16 / 2 * 15 / 2 = 60 MHz. Keep tolerance below MCU's 64 MHz limit.
 * Manufacturer WS2812B-2020-V6 PDF, footer V1.4, timing table on page 4:
 * T0H 220..380 ns, T0L 580..1000 ns; T1H 580..1000 ns,
 * T1L 220..420 ns; each bit >=1250 ns; reset >=280 us.
 * These constants pass the host timing check across +/-3% clock frequency.
 */
#define LB_TIMER_CLOCK_HZ            60000000u
#define LB_WS_PERIOD_TICKS           78u
#define LB_WS_ZERO_HIGH_TICKS        21u
#define LB_WS_ONE_HIGH_TICKS         57u
#define LB_WS_LEADING_SLOTS          2u
#define LB_WS_RESET_SLOTS            256u
#define LB_WS_BITS                   (LB_PIXELS_PER_CHAIN * 24u)
#define LB_WS_SLOTS                  (LB_WS_LEADING_SLOTS + LB_WS_BITS + LB_WS_RESET_SLOTS)
#define LB_WS_DMA_WORDS              (LB_WS_SLOTS * LB_CHAINS)

#endif
