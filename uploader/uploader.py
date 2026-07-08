import serial
import time
import struct
import binascii
import threading
import queue
import sys
import argparse

# Protocol Constants
PREAMBLE_BYTE = 0x7F
PREAMBLE_RX_COUNT = 5
PREAMBLE_TX_COUNT = 12

ESC_BYTE = 0x7D
DELIM_BYTE = 0x7E

HDR_MASK_BASE = 0x80      
HDR_FLAG_64BIT = 0x02    
BROADCAST_ID = 0xFF

# firmware update commands
BOOT_INIT =          0x01
BOOT_CHIP_ERASE =    0x02
BOOT_WRITE_SECTOR =  0x03
BOOT_VERIFY_SECTOR = 0x04
BOOT_EXIT =     0x2B
BOOT_VERIFY_REPORT = 0x85


class CH32V003Bootloader:
    HDR_MASK_TYPE = 0x01   # 0b0000 0001 (0 = Request, 1 = Response)
    
    def __init__(self, port, baud=9600, verbose=False):
        self.verbose = verbose
        self.raw_buffer = bytearray()
        self.got_esc = False
        try:
            self.ser = serial.Serial()
            self.ser.port     = port
            self.ser.baudrate = baud
            self.ser.timeout  = 0.01
            self.ser.stopbits = serial.STOPBITS_TWO

            # keep both control lines low while opening
            self.ser.setDTR(False)
            self.ser.setRTS(False)
            self.ser.open()


            #self.ser = serial.Serial(port, baud, timeout=0.01, stopbits=serial.STOPBITS_TWO)
        except serial.SerialException as e:
            self._log(f"Error opening serial port {port}: {e}")
            return
            
        self.rx_queue = queue.Queue()
        self.stop_thread = False
        self.serial_lock = threading.Lock()
        
        self.thread = threading.Thread(target=self._uart_reader_thread, daemon=True)
        self.thread.start()

    def _log(self, message, end='\n'):
        if self.verbose:
            print(message, end=end)
            sys.stdout.flush()
            
    def close(self):
        self.stop_thread = True
        if self.thread.is_alive():
            self.thread.join()
        self.ser.close()

    # --- Communication Core ---
    def poll_uart_msg(self):
        got_delim = False

        while self.ser.in_waiting > 0:
            b = self.ser.read(1)[0]
            if b == DELIM_BYTE:
                got_delim = True
                self.got_esc = False
                break
            elif b == ESC_BYTE:
                self.got_esc = True
            elif self.got_esc:
                self.raw_buffer.append(b | 0x20)
            else:
                self.raw_buffer.append(b)
        buff = self.raw_buffer
        bufflen = len(buff)
        res = None
        if got_delim and  bufflen > 0:
           len = buff[1] if  bufflen > 1 else 0
           res = {
                    'cmd': buff[0],
                    'len': len,
                    'addr': buff[2] + 256 * buff[3] if bufflen > 3 else 0,
                    'data': buff[4:] if bufflen > 4 else [],
                    'raw': buff
                }
           self.raw_buffer.clear()
        return res
                
    def send_packet(self, cmd, address=None, data=None):
        if data is None: data = []
        buff = bytearray()
        buff.append(cmd)
        if not address:
            buff.append(2)
        else:
            buff.append(4 + len(data))
            buff.append(address & 0xFF)
            buff.append((address >> 8) & 0xFF)
            buff.extend(data)
        encbuff = bytearray()
        for b in buff:
            if b == ESC_BYTE or b == DELIM_BYTE:
                encbuff.append(ESC_BYTE)
                encbuff.append(b & 0xDF)
            else:
                encbuff.append(b)
        encbuff.append(DELIM_BYTE)
        self.ser.write(encbuff)
        self.ser.flush()

    def get_response(self, timeout_ms=1000):
        timeout_ms
        res = None
        while timeout_ms > 0:
            res = self.poll_uart_msg()
            if res:
                break
            time.sleep(0.01)
            timeout_ms -= 10
        return res

    # --- High Level Commands ---

    def send_init(self):
        """Starts upgrade process."""
        self._log(f"Initializing upgrade process...")
        self.send_packet(BOOT_INIT, 0x00)
        resp = self.get_response()
        if resp:
            self.num_devices = resp["addr"]
            self._log(f"Done. {self.num_devices} Devices found")
            return True
        self._log("No response from devices.")
        return False
    
    def send_erase_chip(self):
        """Erase device flash."""
        self._log(f"Erasing device...")
        self.send_packet(BOOT_CHIP_ERASE)
        resp = self.get_response()
        if resp:
            self._log("Done.")
            return True
        self._log("No response from devices.")
        return False
    
    def send_write_sector(self, addr, sector):
        """Write a single 64 bytes sector."""
        self._log(f"Writing sector {addr / 64}...")
        self.send_packet(BOOT_WRITE_SECTOR, addr, sector)
        resp = self.get_response()
        if resp:
            return True
        self._log("No response from devices.")
        return False
    
    def send_verify_sector(self, addr, sector):
        """Verify a single 64 bytes sector."""
        self._log(f"Verifing sector {addr / 64}...")
        self.send_packet(BOOT_VERIFY_SECTOR, addr, sector)
        resp = self.get_response()
        if resp:
            return True
        self._log("No response from devices.")
        return False
    
    def send_verify_report(self):
        """Ask for verificatio0n result."""
        self._log(f"Ask for verification result...")
        self.send_packet(BOOT_VERIFY_REPORT)
        resp = self.get_response()
        if resp:
            num_verify_fail = resp["addr"]
            if self.num_devices == 0:
                self._log("All devices updated successfuly")
            else:
                self._log(f"{num_verify_fail}/{self.num_devices} Devices failed verification")
            return num_verify_fail
        self._log("No response from devices.")
        return -1
    
    def send_exit_boot(self):
        """Exit bootloader."""
        self._log(f"Exit bootloader...")
        self.send_packet(BOOT_EXIT)
        resp = self.get_response()
        if resp:
            self._log("Done.")
            return True
        self._log("No response from devices.")
        return False
       
    def update_firmware(self, firmware_data, fw_id=0):
        if len(firmware_data) % 64 != 0:
            padding = 64 - (len(firmware_data) % 64)
            firmware_data += b'\xFF' * padding

        total_blocks = len(firmware_data) // 64
        self._log(f"Flashing {len(firmware_data)} bytes ({total_blocks} blocks) to FW-ID: {fw_id}")
        
        start_time = time.perf_counter()
        self.send_packet(BROADCAST_ID, BOOT_SILENCE)

        for i, offset in enumerate(range(0, len(firmware_data), 64)):
            chunk = firmware_data[offset:offset+64]
            self._broadcast_update_block(i, chunk, fw_id)
            
            # Progress bar
            percent = (i + 1) / total_blocks * 100
            sys.stdout.write(f"\rWriting Block {i+1}/{total_blocks} [{percent:.1f}%]")
            sys.stdout.flush()

        self.send_packet(BROADCAST_ID, BOOT_UNSILENCE)
        self._log(f"\nFinished in {time.perf_counter() - start_time:.2f}s")


def main():
    parser = argparse.ArgumentParser(description='CH32V003 Bootloader Tool')
    parser.add_argument('--port', '-p', help='COM Port')
    parser.add_argument('--baud', '-b', type=int, default=115200)
    parser.add_argument('-f', '--file', help='Firmware file')    
    
    args = parser.parse_args()

    if not args.file:
        print("Error: -i <file> is required")
        return
    
    if not args.port:
        print("Error: -p <port> is required")
        return
    
    loader = CH32V003Bootloader(args.port, args.baud, verbose=True)

    try:
        with open(args.file, 'rb') as f:
            loader.update_firmware(f.read(), args.fw)

                
    finally:
        loader.close()
        
if __name__ == "__main__":
    main()
    
    