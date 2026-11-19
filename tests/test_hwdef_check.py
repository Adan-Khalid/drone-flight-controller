from fcboard.hwdef_check import dma_assignments, exclusive, unresolved_line

SAMPLE = """
// auto-generated DMA mapping from dma_resolver.py
#define STM32_SPI_SPI1_RX_DMA_STREAM   STM32_DMA_STREAM_ID(1, 0)
#define STM32_SPI_SPI1_TX_DMA_STREAM   STM32_DMA_STREAM_ID(1, 1)
#define STM32_TIM_TIM3_UP_DMA_STREAM   STM32_DMA_STREAM_ID(2, 2)
#define STM32_TIM_TIM3_CH3_DMA_STREAM  STM32_DMA_STREAM_ID(2, 2)
#define STM32_TIM_TIM1_UP_DMA_STREAM   STM32_DMA_STREAM_ID(2, 7) // shared UART7_TX,TIM1_UP
#define STM32_UART_UART7_TX_DMA_STREAM STM32_DMA_STREAM_ID(2, 7) // shared UART7_TX,TIM1_UP
"""


def test_parses_every_assignment_and_sharing():
    a = dma_assignments(SAMPLE)
    assert [x.peripheral for x in a] == ["SPI1_RX", "SPI1_TX", "TIM3_UP", "TIM3_CH3", "TIM1_UP",
                                        "UART7_TX"]
    assert a[0].dma == 1 and a[0].stream == 0
    assert a[4].shared_with == ("UART7_TX", "TIM1_UP")


def test_timer_up_and_capture_on_one_stream_count_as_exclusive():
    ex = exclusive(dma_assignments(SAMPLE), ("SPI1", "TIM3"))
    assert ex == {"SPI1_RX": True, "SPI1_TX": True, "TIM3_UP": True, "TIM3_CH3": True}


def test_sharing_with_another_peripheral_is_not_exclusive():
    clash = SAMPLE + "#define STM32_UART_USART2_RX_DMA_STREAM STM32_DMA_STREAM_ID(1, 0)\n"
    assert exclusive(dma_assignments(clash), ("SPI1",))["SPI1_RX"] is False


def test_unresolved_line_detected():
    assert unresolved_line(SAMPLE) is None
    bad = SAMPLE + "// Note: The following peripherals can't be resolved for DMA: ['TIM4_UP']\n"
    assert "TIM4_UP" in unresolved_line(bad)
