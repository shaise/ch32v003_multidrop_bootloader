#ifndef PACKET_PROTOCOL_H
#define PACKET_PROTOCOL_H

#include <stdint.h>
#include <stddef.h>

#define DELIMITER_BYTE 0x7E
#define ESC_BYTE 0x7D
#define MAX_DATA_LEN 64

#define PROTOFLAG_GOT_ESC      0x01
#define PROTOFLAG_DEFERED_MODE 0x02

#define PROTOCMD_INIT 0x81
#define PROTOCMD_CHIP_ERASE 0x02
#define PROTOCMD_WRITE_SECTOR 0x03
#define PROTOCMD_VERIFY_SECTOR 0x04
#define PROTOCMD_EXIT_BOOT 0x2B
#define PROTOCMD_VERIFY_REPORT 0x85

typedef struct {
    uint8_t command;
    uint8_t packet_len;
    uint16_t address;
    uint8_t data[MAX_DATA_LEN]__attribute__((aligned(4)));;
} Packet_t;



/**
 * @brief Serializes a RESPONSE packet. Encodes the packet and send to tx buffer
 * @param pkt   Packet to send.
 */
void packet_send(Packet_t *pkt);


/**
 * @brief Handles a single incoming byte (supports both Request and Response).
 * @return 1 if a full valid packet was completed (CRC matches), 0 otherwise.
 */
uint8_t Packet_Update_Rx(uint8_t byte, Packet_t *pkt);

/**
 * @brief in defered mode command forwarding is delayed until command is evaluated
 */
uint8_t is_defered_mode(void);

#endif
