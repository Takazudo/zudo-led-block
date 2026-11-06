#include "lb_config.h"
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv)
{
    const double slow = LB_TIMER_CLOCK_HZ * 0.97;
    const double fast = LB_TIMER_CLOCK_HZ * 1.03;
    if (argc == 2 && strcmp(argv[1], "--json") == 0) {
        printf("{\"timer_hz\":%u,\"period_ticks\":%u,\"zero_high_ticks\":%u,\"one_high_ticks\":%u,"
               "\"nominal_bit_ns\":%.6f,\"nominal_T0H_ns\":%.6f,\"nominal_T1H_ns\":%.6f,"
               "\"dma_halfwords\":%u,\"buffer_bytes\":%u,\"complete_reset_low_cells_min\":%u,"
               "\"minimum_reset_us_at_fast_envelope\":%.6f,\"channel_cap\":%u,\"adc_board_revision\":%u,"
               "\"adc_divider_num\":%u,\"adc_divider_den\":%u,\"adc_inverse_gain_num\":%u,\"adc_inverse_gain_den\":%u}\n",
               LB_TIMER_CLOCK_HZ,LB_WS_PERIOD_TICKS,LB_WS_ZERO_HIGH_TICKS,LB_WS_ONE_HIGH_TICKS,
               LB_WS_PERIOD_TICKS*1e9/LB_TIMER_CLOCK_HZ,LB_WS_ZERO_HIGH_TICKS*1e9/LB_TIMER_CLOCK_HZ,
               LB_WS_ONE_HIGH_TICKS*1e9/LB_TIMER_CLOCK_HZ,LB_WS_DMA_WORDS,LB_WS_DMA_WORDS*2u,
               LB_WS_RESET_SLOTS-2u,(LB_WS_RESET_SLOTS-2u)*LB_WS_PERIOD_TICKS*1e6/fast,
               LB_CHANNEL_CAP,LB_ADC_BOARD_REVISION,LB_ADC_DIVIDER_NUM,LB_ADC_DIVIDER_DEN,
               LB_ADC_INVERSE_GAIN_NUM,LB_ADC_INVERSE_GAIN_DEN);
        return 0;
    }
    const unsigned ticks[] = {LB_WS_ZERO_HIGH_TICKS, LB_WS_PERIOD_TICKS-LB_WS_ZERO_HIGH_TICKS,
                              LB_WS_ONE_HIGH_TICKS, LB_WS_PERIOD_TICKS-LB_WS_ONE_HIGH_TICKS,
                              LB_WS_PERIOD_TICKS};
    const char *name[] = {"T0H", "T0L", "T1H", "T1L", "Bit cell"};
    const char *bounds[] = {"220..380", "580..1000", "580..1000", "220..420", ">=1250"};
    puts("# A5 timing derived from the compiled lb_config.h constants\n");
    printf("Timer: %u Hz nominal, period %u ticks; +/-3%% envelope %.0f..%.0f Hz.\n\n",
           LB_TIMER_CLOCK_HZ,LB_WS_PERIOD_TICKS,slow,fast);
    puts("| Signal | Ticks | Nominal ns | Minimum ns (+3% clock) | Maximum ns (-3% clock) | Manufacturer ns |\n|---|---:|---:|---:|---:|---:|");
    for(unsigned i=0;i<5;++i)
        printf("| %s | %u | %.3f | %.3f | %.3f | %s |\n",name[i],ticks[i],ticks[i]*1e9/LB_TIMER_CLOCK_HZ,ticks[i]*1e9/fast,ticks[i]*1e9/slow,bounds[i]);
    printf("\nTwo independent %u-pixel chains, GRB MSB first; %u data cells per chain.\n",LB_PIXELS_PER_CHAIN,LB_WS_BITS);
    printf("DMA: %u interleaved 16-bit values, %u bytes, %u lead + %u data + %u zero-tail slots.\n",
           LB_WS_DMA_WORDS,LB_WS_DMA_WORDS*2u,LB_WS_LEADING_SLOTS,LB_WS_BITS,LB_WS_RESET_SLOTS);
    printf("Tail complete before immediate DMA-stop callback, conservatively excluding two pipeline cells: %u cells; nominal %.3f us, minimum %.3f us. Requirement: >=280 us.\n",
           LB_WS_RESET_SLOTS-2u,(LB_WS_RESET_SLOTS-2u)*LB_WS_PERIOD_TICKS*1e6/LB_TIMER_CLOCK_HZ,(LB_WS_RESET_SLOTS-2u)*LB_WS_PERIOD_TICKS*1e6/fast);
    puts("\nThis calculation covers oscillator frequency tolerance; it does not measure pad/translator/LED waveform, DMA timing under real bus contention or PLL jitter. Scope verification on both chains and the exact LED lot remains required.");
    return 0;
}
