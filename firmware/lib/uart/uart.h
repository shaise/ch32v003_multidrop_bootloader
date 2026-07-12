#ifndef _UART_H
#define _UART_H

#include "stdint.h"

void uart_init(void);
void uart_deinit(void);

void uart_write(uint8_t ch);
uint8_t uart_available(void);
uint8_t uart_tx_ready(void);
uint8_t uart_read(void);
void uart_poll(void);



#endif