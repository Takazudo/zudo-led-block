#include "board.h"
#include <stddef.h>

#if !defined(STM32G031xx)
#error This board port is for STM32G031G8U6TR only.
#endif
#if LB_ADC_BOARD_REVISION != 5u
#error A5 firmware requires the buffered and divided A5 CV input.
#endif

#define PIN_EN       GPIO_PIN_5
#define PIN_FAULT    GPIO_PIN_4
#define PIN_DATA     (GPIO_PIN_6 | GPIO_PIN_7)
#define DATA_MODE_MASK ((3u << (6u * 2u)) | (3u << (7u * 2u)))
#define DATA_MODE_OUT  ((1u << (6u * 2u)) | (1u << (7u * 2u)))
#define DATA_MODE_AF   ((2u << (6u * 2u)) | (2u << (7u * 2u)))

_Static_assert(LB_CHAINS == 2u, "TIM3 burst owns exactly two channels");
_Static_assert(offsetof(TIM_TypeDef, CCR1) == 0x34u, "TIM3 CCR1 burst base");
_Static_assert(offsetof(TIM_TypeDef, CCR2) == 0x38u, "TIM3 CCR2 follows CCR1");
_Static_assert(LB_WS_DMA_WORDS <= 65535u, "DMA counter range");

volatile uint32_t lb_debug_reset_csr;
volatile uint32_t lb_debug_boot_decision;
volatile uint32_t lb_debug_backup_at_boot[2];
volatile uint32_t lb_debug_adc_raw;
volatile uint32_t lb_debug_vref_raw;
volatile uint32_t lb_debug_fault;

static ADC_HandleTypeDef adc;
static DMA_HandleTypeDef dma;
static IWDG_HandleTypeDef watchdog;
static lb_controller_t *controller;
static volatile uint32_t dma_busy;
static bool backup_ready;

void board_reset_safe_outputs(void)
{
    /* Hardware NPN base pulldown already disables VLED during reset. Preload
     * low BEFORE selecting push-pull outputs to avoid an enable/data glitch. */
    RCC->IOPENR |= RCC_IOPENR_GPIOAEN;
    (void)RCC->IOPENR;
    GPIOA->BSRR = (uint32_t)(PIN_EN | PIN_DATA) << 16;
    GPIOA->OTYPER &= ~(PIN_EN | PIN_DATA);
    GPIOA->PUPDR &= ~((3u << (5u * 2u)) | DATA_MODE_MASK);
    GPIOA->MODER = (GPIOA->MODER & ~((3u << (5u * 2u)) | DATA_MODE_MASK)) |
                   (1u << (5u * 2u)) | DATA_MODE_OUT;
    __DSB();
}

static void stop_low(void *unused)
{
    (void)unused;
    /* No HAL abort wait in this path: also called at FAULT IRQ priority 0. */
    TIM3->DIER = 0u;
    TIM3->CR1 &= ~TIM_CR1_CEN;
    DMA1_Channel1->CCR &= ~DMA_CCR_EN;
    DMA1->IFCR = DMA_IFCR_CGIF1;
    TIM3->CCER = 0u;
    TIM3->CCR1 = 0u;
    TIM3->CCR2 = 0u;
    GPIOA->BSRR = (uint32_t)PIN_DATA << 16;
    GPIOA->MODER = (GPIOA->MODER & ~DATA_MODE_MASK) | DATA_MODE_OUT;
    dma_busy = 0u;
    __DMB();
}

static void enable_write(void *unused, bool high)
{
    (void)unused;
    GPIOA->BSRR = high ? PIN_EN : ((uint32_t)PIN_EN << 16);
    __DSB();
}

static uint32_t critical_enter(void *unused)
{
    (void)unused;
    uint32_t key = __get_PRIMASK();
    __disable_irq();
    __DMB();
    return key;
}

static void critical_exit(void *unused, uint32_t key)
{
    (void)unused;
    __DMB();
    __set_PRIMASK(key);
    __ISB();
}

static bool fault_pending(void *unused)
{
    (void)unused;
    return (GPIOA->IDR & PIN_FAULT) == 0u || (EXTI->FPR1 & PIN_FAULT) != 0u;
}

static bool marker_commit(void *unused, lb_marker_t marker, lb_fault_t reason)
{
    (void)unused;
    if (!backup_ready) return false;
    /* Either interrupted write leaves a nonzero/corrupt pair, which inhibits.
     * NEVER use RCC_BDCR.BDRST, HAL_RTC_Init or a backup erase in normal boot. */
    TAMP->BKP0R = (uint32_t)marker;
    TAMP->BKP1R = ~(uint32_t)marker;
    TAMP->BKP2R = (uint32_t)reason;
    __DSB();
    if (reason != LB_FAULT_NONE) lb_debug_fault = (uint32_t)reason;
    return TAMP->BKP0R == (uint32_t)marker && TAMP->BKP1R == ~(uint32_t)marker;
}

static void dma_done(DMA_HandleTypeDef *handle)
{
    (void)handle;
    /* Two preload-pipeline slots are conservatively excluded from the reset
     * tail. At least254 complete low cells have elapsed (>320us at+3%). */
    stop_low(NULL);
}

static void dma_error(DMA_HandleTypeDef *handle)
{
    (void)handle;
    if (controller) lb_guard_trip(&controller->guard, LB_FAULT_DMA);
    else { enable_write(NULL, false); stop_low(NULL); }
}

static bool transfer_start(void *unused, const uint16_t *data, size_t words)
{
    (void)unused;
    if (dma_busy != 0u || words != LB_WS_DMA_WORDS || !data) return false;
    TIM3->CR1 = TIM_CR1_ARPE;
    TIM3->DIER = 0u;
    TIM3->PSC = 0u;
    TIM3->ARR = LB_WS_PERIOD_TICKS - 1u;
    TIM3->CNT = 0u;
    TIM3->CCR1 = 0u;
    TIM3->CCR2 = 0u;
    TIM3->CCMR1 = TIM_CCMR1_OC1PE | TIM_CCMR1_OC2PE |
                   (6u << TIM_CCMR1_OC1M_Pos) | (6u << TIM_CCMR1_OC2M_Pos);
    TIM3->CCER = TIM_CCER_CC1E | TIM_CCER_CC2E;
    TIM3->DCR = (13u << TIM_DCR_DBA_Pos) | (1u << TIM_DCR_DBL_Pos);
    /* UG latches all initial zero values; update DMA is still disabled. */
    TIM3->EGR = TIM_EGR_UG;
    TIM3->SR = 0u;
    dma.State = HAL_DMA_STATE_READY; /* abort path disables peripheral directly */
    dma.ErrorCode = HAL_DMA_ERROR_NONE;
    dma.Lock = HAL_UNLOCKED;
    if (HAL_DMA_Start_IT(&dma, (uint32_t)(uintptr_t)data,
                         (uint32_t)(uintptr_t)&TIM3->DMAR, (uint32_t)words) != HAL_OK) return false;
    GPIOA->BSRR = (uint32_t)PIN_DATA << 16;
    GPIOA->MODER = (GPIOA->MODER & ~DATA_MODE_MASK) | DATA_MODE_AF;
    dma_busy = 1u;
    __DMB();
    TIM3->DIER = TIM_DIER_UDE;
    TIM3->CR1 |= TIM_CR1_CEN;
    return true;
}

static bool transfer_busy(void *unused) { (void)unused; return dma_busy != 0u; }

lb_io_t board_io(void)
{
    lb_io_t io = { NULL, critical_enter, critical_exit, fault_pending, enable_write,
                   stop_low, marker_commit, transfer_start, transfer_busy };
    return io;
}

static bool clock_init(void)
{
    __HAL_RCC_PWR_CLK_ENABLE();
    if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK) return false;
    RCC_OscInitTypeDef osc = {0};
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSI | RCC_OSCILLATORTYPE_LSI;
    osc.HSIState = RCC_HSI_ON;
    osc.HSIDiv = RCC_HSI_DIV1;
    osc.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    osc.LSIState = RCC_LSI_ON;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSI;
    osc.PLL.PLLM = RCC_PLLM_DIV2;
    osc.PLL.PLLN = 15u;
    osc.PLL.PLLP = RCC_PLLP_DIV2;
    osc.PLL.PLLQ = RCC_PLLQ_DIV2;
    osc.PLL.PLLR = RCC_PLLR_DIV2;
    if (HAL_RCC_OscConfig(&osc) != HAL_OK) return false;
    RCC_ClkInitTypeDef clock = {0};
    clock.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_PCLK1;
    clock.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clock.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clock.APB1CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&clock, FLASH_LATENCY_2) != HAL_OK) return false;
    return HAL_RCC_GetHCLKFreq() == LB_TIMER_CLOCK_HZ;
}

static bool adc_init(void)
{
    __HAL_RCC_ADC_CLK_ENABLE();
    adc.Instance = ADC1;
    adc.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV4; /* 15 MHz nominal */
    adc.Init.Resolution = ADC_RESOLUTION_12B;
    adc.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    adc.Init.ScanConvMode = ADC_SCAN_ENABLE;
    adc.Init.EOCSelection = ADC_EOC_SINGLE_CONV;
    adc.Init.LowPowerAutoWait = ENABLE; /* prevents scan overrun while CPU reads */
    adc.Init.LowPowerAutoPowerOff = DISABLE;
    adc.Init.ContinuousConvMode = DISABLE;
    adc.Init.NbrOfConversion = 2;
    adc.Init.DiscontinuousConvMode = DISABLE;
    adc.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    adc.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
    adc.Init.DMAContinuousRequests = DISABLE;
    adc.Init.Overrun = ADC_OVR_DATA_PRESERVED;
    adc.Init.SamplingTimeCommon1 = ADC_SAMPLETIME_160CYCLES_5;
    adc.Init.SamplingTimeCommon2 = ADC_SAMPLETIME_160CYCLES_5;
    adc.Init.OversamplingMode = DISABLE;
    adc.Init.TriggerFrequencyMode = ADC_TRIGGER_FREQ_LOW;
    if (HAL_ADC_Init(&adc) != HAL_OK || HAL_ADCEx_Calibration_Start(&adc) != HAL_OK) return false;
    ADC_ChannelConfTypeDef channel = {0};
    channel.Channel = ADC_CHANNEL_0;
    channel.Rank = ADC_REGULAR_RANK_1;
    channel.SamplingTime = ADC_SAMPLINGTIME_COMMON_1;
    if (HAL_ADC_ConfigChannel(&adc, &channel) != HAL_OK) return false;
    channel.Channel = ADC_CHANNEL_VREFINT;
    channel.Rank = ADC_REGULAR_RANK_2;
    if (HAL_ADC_ConfigChannel(&adc, &channel) != HAL_OK) return false;
    HAL_Delay(1); /* exceeds documented VREFINT startup stabilization */
    return true;
}

bool board_init(void)
{
    if (HAL_Init() != HAL_OK || !clock_init()) return false;
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_TIM3_CLK_ENABLE();
    __HAL_RCC_DMA1_CLK_ENABLE();
    __HAL_RCC_RTCAPB_CLK_ENABLE();
    HAL_PWR_EnableBkUpAccess();
    if ((PWR->CR1 & PWR_CR1_DBP) == 0u) return false;
    if ((RCC->BDCR & RCC_BDCR_RTCSEL) == 0u) RCC->BDCR |= RCC_RTCCLKSOURCE_LSI;
    __HAL_RCC_RTC_ENABLE();
    backup_ready = true;

    GPIO_InitTypeDef pin = {0};
    pin.Pin = GPIO_PIN_2 | GPIO_PIN_3;
    pin.Mode = GPIO_MODE_INPUT;
    pin.Pull = GPIO_NOPULL; /* board has 10kohm pull-ups */
    HAL_GPIO_Init(GPIOA, &pin);
    pin.Pin = GPIO_PIN_0;
    pin.Mode = GPIO_MODE_ANALOG;
    HAL_GPIO_Init(GPIOA, &pin);
    pin.Pin = PIN_FAULT;
    pin.Mode = GPIO_MODE_IT_FALLING;
    HAL_GPIO_Init(GPIOA, &pin);
    /* Configure AF1 mapping without changing the safe output mode yet. */
    GPIOA->AFR[0] = (GPIOA->AFR[0] & ~((15u << 24) | (15u << 28))) |
                    ((uint32_t)GPIO_AF1_TIM3 << 24) | ((uint32_t)GPIO_AF1_TIM3 << 28);
    GPIOA->OSPEEDR = (GPIOA->OSPEEDR & ~DATA_MODE_MASK) | DATA_MODE_OUT; /* medium */

    dma.Instance = DMA1_Channel1;
    dma.Init.Request = DMA_REQUEST_TIM3_UP;
    dma.Init.Direction = DMA_MEMORY_TO_PERIPH;
    dma.Init.PeriphInc = DMA_PINC_DISABLE;
    dma.Init.MemInc = DMA_MINC_ENABLE;
    dma.Init.PeriphDataAlignment = DMA_PDATAALIGN_HALFWORD;
    dma.Init.MemDataAlignment = DMA_MDATAALIGN_HALFWORD;
    dma.Init.Mode = DMA_NORMAL;
    dma.Init.Priority = DMA_PRIORITY_HIGH;
    if (HAL_DMA_Init(&dma) != HAL_OK) return false;
    dma.XferCpltCallback = dma_done;
    dma.XferErrorCallback = dma_error;
    dma.XferHalfCpltCallback = NULL;
    stop_low(NULL);
    if (!adc_init()) return false;

    watchdog.Instance = IWDG;
    watchdog.Init.Prescaler = IWDG_PRESCALER_32;
    watchdog.Init.Reload = 999u; /* approx1s; LSI tolerance applies */
    watchdog.Init.Window = IWDG_WINDOW_DISABLE;
    if (HAL_IWDG_Init(&watchdog) != HAL_OK) return false;
    return true;
}

lb_boot_decision_t board_boot_decision(uint32_t csr)
{
    uint32_t causes = 0;
    if (csr & RCC_CSR_PWRRSTF) causes |= LB_RESET_POWER;
    if (csr & RCC_CSR_PINRSTF) causes |= LB_RESET_PIN;
    if (csr & RCC_CSR_SFTRSTF) causes |= LB_RESET_SOFTWARE;
    if (csr & RCC_CSR_IWDGRSTF) causes |= LB_RESET_IWDG;
    if (csr & RCC_CSR_WWDGRSTF) causes |= LB_RESET_WWDG;
    if (csr & RCC_CSR_OBLRSTF) causes |= LB_RESET_OPTION;
    if (csr & RCC_CSR_LPWRRSTF) causes |= LB_RESET_LOWPOWER;
    lb_debug_backup_at_boot[0] = TAMP->BKP0R;
    lb_debug_backup_at_boot[1] = TAMP->BKP1R;
    lb_boot_decision_t decision = lb_boot_classify(causes, lb_debug_backup_at_boot[0], lb_debug_backup_at_boot[1]);
    lb_debug_boot_decision = (uint32_t)decision;
    /* Clear AFTER snapshot/classification; do not carry a stale PWRRSTF forward. */
    __HAL_RCC_CLEAR_RESET_FLAGS();
    return decision;
}

void board_attach_controller(lb_controller_t *c)
{
    controller = c;
    HAL_NVIC_SetPriority(EXTI4_15_IRQn, 0, 0);
    HAL_NVIC_SetPriority(DMA1_Channel1_IRQn, 1, 0);
    /* Never clear a latched falling edge here: guard inspects it before enable. */
    HAL_NVIC_EnableIRQ(EXTI4_15_IRQn);
    HAL_NVIC_EnableIRQ(DMA1_Channel1_IRQn);
    if (fault_pending(NULL)) lb_guard_trip(&controller->guard, LB_FAULT_POWER_SWITCH);
}

bool board_adc_pair(uint16_t *cv, uint16_t *vref)
{
    if (HAL_ADC_Start(&adc) != HAL_OK) return false;
    if (HAL_ADC_PollForConversion(&adc, 2u) != HAL_OK) { (void)HAL_ADC_Stop(&adc); return false; }
    *cv = (uint16_t)HAL_ADC_GetValue(&adc);
    if (HAL_ADC_PollForConversion(&adc, 2u) != HAL_OK) { (void)HAL_ADC_Stop(&adc); return false; }
    *vref = (uint16_t)HAL_ADC_GetValue(&adc);
    bool ok = HAL_ADC_Stop(&adc) == HAL_OK && HAL_ADC_GetError(&adc) == HAL_ADC_ERROR_NONE;
    lb_debug_adc_raw = *cv;
    lb_debug_vref_raw = *vref;
    return ok;
}

uint8_t board_switch_ab(void)
{
    uint32_t input = GPIOA->IDR;
    return (uint8_t)(((input & GPIO_PIN_2) != 0u ? 2u : 0u) |
                     ((input & GPIO_PIN_3) != 0u ? 1u : 0u));
}

void board_watchdog_feed(void) { (void)HAL_IWDG_Refresh(&watchdog); }

void EXTI4_15_IRQHandler(void)
{
    if ((EXTI->FPR1 & PIN_FAULT) != 0u || (GPIOA->IDR & PIN_FAULT) == 0u) {
        /* Software latch is set and power removed before acknowledging the IRQ. */
        if (controller) lb_guard_trip(&controller->guard, LB_FAULT_POWER_SWITCH);
        else { enable_write(NULL, false); stop_low(NULL); }
        EXTI->FPR1 = PIN_FAULT;
    }
}

void DMA1_Channel1_IRQHandler(void) { HAL_DMA_IRQHandler(&dma); }
void SysTick_Handler(void) { HAL_IncTick(); }

_Noreturn void board_fail(lb_fault_t reason)
{
    __disable_irq();
    board_reset_safe_outputs();
    if (controller) lb_guard_trip(&controller->guard, reason);
    else { enable_write(NULL, false); stop_low(NULL); (void)marker_commit(NULL, LB_MARK_FAULT, reason); }
    /* No feed: an already running watchdog resets into the retained lockout. */
    for (;;) __WFI();
}

void HardFault_Handler(void) { board_fail(LB_FAULT_CPU); }
void NMI_Handler(void) { board_fail(LB_FAULT_CPU); }
