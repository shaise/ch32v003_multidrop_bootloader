#include "uart.h"
#include <ch32v00x.h>

#define TXBUFF_SIZE 64
#define TXBUFF_MASK 0x3F
uint8_t tx_buffer[TXBUFF_SIZE];
uint8_t tx_head = 0;
uint8_t tx_tail = 0;
uint8_t tx_full = 0;

static inline uint8_t tx_bytes_available(void)
{
    return tx_full || tx_head != tx_tail;
}

static inline void tx_push(uint8_t byte)
{
    if (!tx_full)
    {
        tx_buffer[tx_head] = byte;
        tx_head++;
        tx_head &= TXBUFF_MASK;
        tx_full = tx_head == tx_tail;
    }
}

static inline uint8_t tx_pop() // assumes byte available - no checks
{
    uint8_t res = tx_buffer[tx_tail];
    tx_tail++;
    tx_tail &= TXBUFF_MASK;
    tx_full = 0;
    return res;
}

/**
 * @brief Check and send available tx bytes  
 */
void uart_poll(void)
{
    if ((USART1->STATR & USART_FLAG_TXE) != (uint16_t)RESET)
    {
        if (tx_bytes_available())
        {
            USART1->DATAR = tx_pop();
        }
    }
}

/**
 * @brief Write outgoing data
 */
void uart_write(uint8_t ch){
    //may use USART_FLAG_TC instead?.
    if ((USART1->STATR & USART_FLAG_TXE) != (uint16_t)RESET)
    {
        if (tx_bytes_available())
        {
            USART1->DATAR = tx_pop();
            tx_push(ch);
        }
        else
            USART1->DATAR = ch;
    }
    else
        tx_push(ch);
}

/**
 * @brief check if we got incomming data
 */
uint8_t uart_available(void){
    return (USART1->STATR & USART_FLAG_RXNE) != (uint16_t)RESET;
}

/**
 * @brief check if uart is ready to send a byte
 */
uint8_t uart_tx_ready(void){
    return (USART1->STATR & USART_FLAG_TXE) != (uint16_t)RESET;
}

/**
 * @brief Read incomming data
 */
uint8_t uart_read(void){
    return (uint8_t)USART1->DATAR;
}


/**
 * @brief Init UART. Fixed baudrate to save flash. 
 */
void uart_init(void){
    //Configure UART
    // 9600 bps @ 8Mhz
    // Half-duplex
    // Eanabled with Tx and RX 
    USART1->BRR = 208;
    // USART1->CTLR3 = USART_CTLR3_HDSEL; 
    USART1->CTLR1 = USART_CTLR1_UE | USART_CTLR1_TE | USART_CTLR1_RE;
}

void uart_deinit(void){
    //Disable Uart.
    USART1->CTLR1 = 0;
    // USART1->CTLR3 = 0; 
}
