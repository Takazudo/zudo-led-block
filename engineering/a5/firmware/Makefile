HOST_CC ?= cc
ARM_PREFIX ?= arm-none-eabi-
ARM_CC := $(ARM_PREFIX)gcc
ARM_OBJCOPY := $(ARM_PREFIX)objcopy
ARM_SIZE := $(ARM_PREFIX)size
BUILD ?= build
CUBE ?= vendor/STM32CubeG0
HAL := $(CUBE)/Drivers/STM32G0xx_HAL_Driver
DEVICE := $(CUBE)/Drivers/CMSIS/Device/ST/STM32G0xx
CORE := $(CUBE)/Drivers/CMSIS/Include
BOARD := platform/stm32g031
HOST_FLAGS := -std=c11 -O2 -g -Wall -Wextra -Werror -Wpedantic -Iinclude
ARM_FLAGS := -std=c11 -Os -g3 -mcpu=cortex-m0plus -mthumb -ffreestanding -fno-builtin \
             -ffunction-sections -fdata-sections -fstack-usage -Wall -Wextra \
             -ffile-prefix-map=$(CURDIR)=. -fdebug-prefix-map=$(CURDIR)=. \
             -DSTM32G031xx -DUSE_HAL_DRIVER -Iinclude -I$(BOARD) -I$(HAL)/Inc \
             -I$(DEVICE)/Include -I$(CORE)
HAL_SOURCES := $(addprefix $(HAL)/Src/,stm32g0xx_hal.c stm32g0xx_hal_rcc.c \
               stm32g0xx_hal_rcc_ex.c stm32g0xx_hal_gpio.c stm32g0xx_hal_cortex.c \
               stm32g0xx_hal_dma.c stm32g0xx_hal_dma_ex.c stm32g0xx_hal_flash.c \
               stm32g0xx_hal_flash_ex.c stm32g0xx_hal_pwr.c stm32g0xx_hal_pwr_ex.c \
               stm32g0xx_hal_adc.c stm32g0xx_hal_adc_ex.c stm32g0xx_hal_iwdg.c)
ARM_SOURCES := src/light_block.c $(BOARD)/board.c $(BOARD)/main.c $(BOARD)/runtime.c \
               $(DEVICE)/Source/Templates/system_stm32g0xx.c $(HAL_SOURCES)
ARM_OBJECTS := $(addprefix $(BUILD)/arm/,$(ARM_SOURCES:.c=.o))
STARTUP := $(BUILD)/arm/startup.o

.PHONY: all test test-sanitize arm timing clean
all: test

$(BUILD)/test_firmware: tests/test_firmware.c src/light_block.c include/light_block.h include/lb_config.h
	@mkdir -p $(dir $@)
	$(HOST_CC) $(HOST_FLAGS) src/light_block.c tests/test_firmware.c -o $@
test: $(BUILD)/test_firmware
	./$(BUILD)/test_firmware

test-sanitize:
	@mkdir -p $(BUILD)
	$(HOST_CC) $(HOST_FLAGS) -O1 -fsanitize=address,undefined -fno-omit-frame-pointer src/light_block.c tests/test_firmware.c -o $(BUILD)/test_firmware_sanitize
	./$(BUILD)/test_firmware_sanitize

$(BUILD)/arm/%.o: %.c include/light_block.h include/lb_config.h $(BOARD)/stm32g0xx_hal_conf.h
	@mkdir -p $(dir $@)
	$(ARM_CC) $(ARM_FLAGS) -MMD -MP -c $< -o $@
$(STARTUP): $(DEVICE)/Source/Templates/gcc/startup_stm32g031xx.s
	@mkdir -p $(dir $@)
	$(ARM_CC) -mcpu=cortex-m0plus -mthumb -c $< -o $@
$(BUILD)/light_block_A5.elf: $(ARM_OBJECTS) $(STARTUP) $(BOARD)/stm32g031g8.ld
	$(ARM_CC) -mcpu=cortex-m0plus -mthumb -nostdlib -Wl,--gc-sections \
	  -Wl,-Map=$(BUILD)/light_block_A5.map -Wl,--print-memory-usage \
	  -T$(BOARD)/stm32g031g8.ld $(ARM_OBJECTS) $(STARTUP) -lgcc -o $@
	$(ARM_SIZE) $@
arm: $(BUILD)/light_block_A5.elf
	$(ARM_OBJCOPY) -O ihex $< $(BUILD)/light_block_A5.hex
	$(ARM_OBJCOPY) -O binary $< $(BUILD)/light_block_A5.bin

$(BUILD)/timing_report: tests/timing_report.c include/lb_config.h
	@mkdir -p $(dir $@)
	$(HOST_CC) $(HOST_FLAGS) $< -o $@
timing: $(BUILD)/timing_report
	./$(BUILD)/timing_report

clean:
	rm -rf $(BUILD)

-include $(ARM_OBJECTS:.o=.d)
