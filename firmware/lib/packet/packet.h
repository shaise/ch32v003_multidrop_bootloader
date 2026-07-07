#ifndef PACKET_PROTOCOL_H
#define PACKET_PROTOCOL_H

#include <stdint.h>
#include <stddef.h>

#define DELIMITER_BYTE 0x7E
#define ESC_BYTE 0x7D
#define MAX_DATA_LEN 64

#define PROTOFLAG_GOT_ESC      0x01
#define PROTOFLAG_DEFERED_MODE 0x02

#define PROTOCMD_INIT 0x01
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
 * @brief Serializes a RESPONSE packet .
 * @note Only 8bit addressing supported.
 * @param buffer   Output buffer where the serialized stream will be stored.
 * @param node_id  The 8-bit destination address/node identifier.
 * @param cmd      The command byte to be executed by the receiver.
 * @param data     Pointer to the payload data buffer (can be NULL if datalen is 0).
 * @param datalen  Length of the payload (0-255).
 * @return uint32_t Total number of bytes written to the buffer (including preambles, header, and CRC).
 */
uint32_t packet_serialize(uint8_t* buffer,
    uint8_t node_id, 
    uint8_t cmd, uint8_t* data, uint8_t datalen);

/**
 * @brief Handles a single incoming byte (supports both Request and Response).
 * @return 1 if a full valid packet was completed (CRC matches), 0 otherwise.
 */
uint8_t Packet_Update_Rx(uint8_t byte, Packet_t *pkt);

/**
 * @brief Get total number of sync chars found
 */
uint32_t get_packet_total_sync_count(void);

#endif
