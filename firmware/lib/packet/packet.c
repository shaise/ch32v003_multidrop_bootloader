#include "packet.h"
#include "crc32.h"


typedef enum { 
    STATE_IDLE, STATE_HDR, STATE_ADDR, STATE_CMD, STATE_LEN, STATE_DATA, STATE_CRC 
} RxState_t;


#define HDR_MASK_BASE       0x80 // Top 6 bits are 100000
#define HDR_FLAG_ADR_128BIT 0x02 // Bit 1
#define HDR_MASK_TYPE       0x01 // Bit 0


/**
 * @brief Serialize a packet into a buffer.
 */
uint32_t packet_serialize(uint8_t* buffer,
    uint8_t node_id, 
    uint8_t cmd, uint8_t* data, uint8_t datalen)
{
    return 0;
}

volatile uint8_t protocol_flags = 0;
volatile uint8_t rx_index = 0;

uint32_t get_packet_total_sync_count(void){
    return 0;
}

uint8_t Packet_Update_Rx(uint8_t byte, Packet_t *pkt) {
    static uint8_t index ;
    static uint8_t crc_buf[4];
    static uint32_t crc_state;

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

