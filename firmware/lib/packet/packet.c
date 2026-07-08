#include "packet.h"
#include "uart.h"

typedef enum { 
    STATE_IDLE, STATE_HDR, STATE_ADDR, STATE_CMD, STATE_LEN, STATE_DATA, STATE_CRC 
} RxState_t;


#define HDR_MASK_BASE       0x80 // Top 6 bits are 100000
#define HDR_FLAG_ADR_128BIT 0x02 // Bit 1
#define HDR_MASK_TYPE       0x01 // Bit 0


/**
 * @brief Serialize a packet into tx buffer.
 */
void packet_send(Packet_t *pkt)
{
    uint8_t *ptr = (uint8_t *)pkt;
    for (int i = 0; i < pkt->packet_len; i++, ptr++)
    {
        uint8_t byte = *ptr;
        if (byte == DELIMITER_BYTE || byte == ESC_BYTE) {
            uart_write(ESC_BYTE);
            byte &= ~0x20;
        } 
        uart_write(byte);
    }
    uart_write(DELIMITER_BYTE);
}

volatile uint8_t protocol_flags = 0;
volatile uint8_t rx_index = 0;

uint8_t is_defered_mode(void)
{
    return protocol_flags & PROTOFLAG_DEFERED_MODE;
}

uint8_t Packet_Update_Rx(uint8_t byte, Packet_t *pkt) {
    // --- Resync Logic ---
    // Always active to detect resync.
    if (byte == DELIMITER_BYTE) {
        uint8_t valid_packet = rx_index > 1 && rx_index == pkt->packet_len;
        rx_index = 0;
        protocol_flags &= ~PROTOFLAG_DEFERED_MODE;
        return valid_packet;
    } else if (byte == ESC_BYTE) {
        protocol_flags |= PROTOFLAG_GOT_ESC;
        return 0;
    } else if (protocol_flags & PROTOFLAG_GOT_ESC) {
        protocol_flags &= ~PROTOFLAG_GOT_ESC;
        byte |= 0x20;
    }
    
    if (rx_index == 0 && (byte & 0x80))
        protocol_flags |= PROTOFLAG_DEFERED_MODE;

    uint8_t *pkt_addr = (uint8_t *)pkt;
    pkt_addr[rx_index] = byte;

    return 0;
}

