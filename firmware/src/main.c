#include <ch32v00x.h>
#include <stdint.h>
#include <stddef.h>
#include "flash.h"
#include "crc32.h"
#include "packet.h"
#include "uart.h"

//-----------------------------------------------------------------
#define BOOTFLAG_VERIFY_ERROR     0x01
#define BOOTFLAG_UPGRADE_COMPLETE 0x01
//-----------------------------------------------------------------

uint32_t memcmp64(const uint8_t *data1, const uint8_t *data2);
void GetChipID64(uint8_t *dest);
void bootloader_start_app(void);
void process_packet(Packet_t* rx);
void initialize(void);
void deinitilize(void);

Packet_t packet;
uint32_t boot_exit = 0;
uint8_t boot_flags = 0;

/**
 * @brief Fast variant to compare 64byte values.
 */
uint32_t memcmp64(const uint8_t *data1, const uint8_t *data2) {
    // use 32bit to take sligtly less flash.
    const uint32_t *p1 = (const uint32_t *)data1;
    const uint32_t *p2 = (const uint32_t *)data2;
    for (int i = 0; i < 16; i++)
    {
        if (p1[i] != p2[i]) return 0;
    }
    return 1;
}


/**
 * @brief Start the applicaton
 */
void bootloader_start_app(void){
    RCC_ClearFlag();
    flash_boot_mode_user();
    NVIC_SystemReset();

}

/**
 * @brief Process incomming packet
 */
void process_packet(Packet_t* rx){
    //fetch info
    const uint8_t cmd = rx->command;

    if (cmd == PROTOCMD_INIT) {
        boot_flags = 0;
        rx->address++;
        packet_send(rx);
    } else if (cmd == PROTOCMD_VERIFY_SECTOR) {
        uint8_t *adr = (uint8_t *)(0x08000000u + rx->address);
        if (!memcmp64(adr, rx->data))
            boot_flags |= BOOTFLAG_VERIFY_ERROR;
    } else if (cmd == PROTOCMD_VERIFY_REPORT) {
        if (boot_flags & BOOTFLAG_VERIFY_ERROR)
            rx->address++;
        else
            boot_flags |= BOOTFLAG_UPGRADE_COMPLETE;
    } else if(cmd == PROTOCMD_EXIT_BOOT){
        boot_exit=1;
    } else if (! (boot_flags & BOOTFLAG_UPGRADE_COMPLETE)) {
        // write commands only if upgrade was not completed
        if (cmd == PROTOCMD_CHIP_ERASE) {
            flash_bulk_erase();
        } else if (cmd == PROTOCMD_WRITE_SECTOR) {
            uint32_t adr = 0x08000000u + rx->address;
            // flash_erase(adr);
            flash_write(adr, &rx->data[4]);  
        } 
    }
}

/**
 * @brief initialize hardware
 */
void initialize(void){
    //Clock init
    //  HSI on, HSItrim 0x10
    //  Systclk / 3 => 8Mhz
    //  No wait states
    RCC->CTLR = 0x00000001 | (0x10<<3);
    RCC->CFGR0 = RCC_HPRE_DIV3;
    //FLASH->ACTLR = 0x00000000; //0x00 at Reset, no need to change.

    //Enable Clocks blocks
    RCC->APB2PCENR |= RCC_IOPDEN | RCC_USART1EN | RCC_AFIOEN;

    //Remapping:
    //  UARTTX to PD6, 
    //  PA-PA2 as GPIO
    AFIO->PCFR1 = 0x00208000;

    //GPIOD config
    // PD6 Alternate Function Open-Drain (Mode 3, CNF 3)
    // PD1 pull-up for debugging.
    GPIOD->CFGLR = 0x4F444484;

    uart_init();
}

/**
 * @brief Deintilize hardware
 */
void deinitilize(void){
    //Restore GPIOD config
    GPIOD->CFGLR = 0x44444484;

    uart_deinit();
}


/**
 * @brief Bootloader main.
 */
int main(){
    initialize();
    boot_exit = 1<<20;       //~4.5 seconds
    

    while (1){        
        //Handle incomming data.
        if(uart_available()){
            uint8_t rx = uart_read();
            if (!is_defered_mode())
                uart_write(rx);
            if(Packet_Update_Rx(rx, &packet)){
                process_packet(&packet);
            }
        }
        uart_poll();

        if(boot_exit) {
            deinitilize();
            bootloader_start_app();
        }
    }
}

