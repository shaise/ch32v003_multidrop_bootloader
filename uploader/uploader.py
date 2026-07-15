import serial
import time
import struct
import binascii
import threading
import queue
import sys
import argparse
import traceback

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
BOOT_INIT =          0x81
BOOT_CHIP_ERASE =    0x02
BOOT_WRITE_SECTOR =  0x03
BOOT_VERIFY_SECTOR = 0x04
BOOT_EXIT =     0x2B
BOOT_VERIFY_REPORT = 0x85


class CH32V003Bootloader:
    HDR_MASK_TYPE = 0x01   # 0b0000 0001 (0 = Request, 1 = Response)
    
    def __init__(self, port, baud=115200, verbose=0):
        self.verbose = verbose
        self.raw_buffer = bytearray()
        self.got_esc = False
        try:
            self.ser = serial.Serial()
            self.ser.port     = port
            self.ser.baudrate = baud
            self.ser.timeout  = 1
            self.ser.stopbits = serial.STOPBITS_ONE

            # keep both control lines low while opening
            self.ser.setDTR(False)
            self.ser.setRTS(False)
            self.ser.open()


            #self.ser = serial.Serial(port, baud, timeout=0.01, stopbits=serial.STOPBITS_TWO)
        except serial.SerialException as e:
            self._log(f"Error opening serial port {port}: {e}")
            return
            
        # self.rx_queue = queue.Queue()
        # self.stop_thread = False
        # self.serial_lock = threading.Lock()
        
        # self.thread = threading.Thread(target=self._uart_reader_thread, daemon=True)
        # self.thread.start()

    def _log(self, message, level = 0, end='\n'):
        if self.verbose >= level:
            print(message, end=end)
            sys.stdout.flush()
            
    def close(self):
        # self.stop_thread = True
        # if self.thread.is_alive():
        #     self.thread.join()
        self.ser.close()

    def validate_response(self, sent_msg, recv_msg):
        # if cmd < 0x80 entire data must be the same
        if sent_msg[0] < 0x80:
            return sent_msg == recv_msg
        # else, only, cmd and length should be the same
        if len(recv_msg) < 4:
            return False
        return sent_msg[:2] == recv_msg[:2]

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
                self.got_esc = False
            else:
                self.raw_buffer.append(b)
        buff = self.raw_buffer
        bufflen = len(buff)
        res = None
        if got_delim and  bufflen > 0:
           length = buff[1] if  bufflen > 1 else 0
           res = {
                    'cmd': buff[0],
                    'len': length,
                    'addr': buff[2] + 256 * buff[3] if bufflen > 3 else 0,
                    'data': buff[4:] if bufflen > 4 else [],
                    'raw': buff.copy()
                }
           self._log(f"(<{bufflen}): {self.raw_buffer.hex(' ')}", level=2)
           self.raw_buffer.clear()
        return res
                
    def send_packet(self, cmd, address=None, data=None):
        if data is None: data = []
        buff = bytearray()
        buff.append(cmd)
        if address is None:
            buff.append(2)
        else:
            buff.append(4 + len(data))
            buff.append(address & 0xFF)
            buff.append((address >> 8) & 0xFF)
            buff.extend(data)
        self.sent_msg = buff
        encbuff = bytearray()
        for b in buff:
            if b == ESC_BYTE or b == DELIM_BYTE:
                encbuff.append(ESC_BYTE)
                encbuff.append(b & 0xDF)
            else:
                encbuff.append(b)
        encbuff.append(DELIM_BYTE)
        self._log(f"(>{len(buff)}): {encbuff.hex(' ')}", level=2)
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
        if not res:
            self._log("No response from devices.")
        elif not self.validate_response(self.sent_msg, res['raw']):
            self._log(f"sent: {self.sent_msg.hex(' ')}", level=1)
            self._log(f"recv: {res['raw'].hex(' ')}", level=1)
            self._log("Invalid returned message.")
            res = None
        return res

    # --- High Level Commands ---

    def send_init(self):
        """Starts upgrade process."""
        self._log(f"Initializing upgrade process... ", end="")
        self.send_packet(BOOT_INIT, 0x00)
        resp = self.get_response()
        if resp:
            print(resp)
            self.num_devices = resp["addr"]
            self._log(f"Done. {self.num_devices} Devices found")
            return True
        return False
    
    def send_erase_chip(self):
        """Erase device flash."""
        self._log(f"Erasing device... ", end="")
        self.send_packet(BOOT_CHIP_ERASE)
        resp = self.get_response()
        if resp:
            self._log("Done.")
            time.sleep(0.01)
            return True
        return False
    
    def send_write_sector(self, addr, sector):
        """Write a single 64 bytes sector."""
        secid = int(addr / 64)
        self._log(f"Writing sector {secid}...", level=1)
        self.send_packet(BOOT_WRITE_SECTOR, addr, sector)
        resp = self.get_response()
        if resp:
            time.sleep(0.01)
            return True
        return False
    
    def send_verify_sector(self, addr, sector):
        """Verify a single 64 bytes sector."""
        secid = int(addr / 64)
        self._log(f"Verifing sector {secid}...", level = 1)
        self.send_packet(BOOT_VERIFY_SECTOR, addr, sector)
        resp = self.get_response()
        if resp:
            return True
        return False
    
    def send_verify_report(self):
        """Ask for verificatio0n result."""
        self._log(f"Ask for verification result...", end = " ")
        self.send_packet(BOOT_VERIFY_REPORT, 0x0)
        resp = self.get_response()
        if resp:
            num_verify_fail = resp["addr"]
            if num_verify_fail == 0:
                self._log("All devices updated successfuly!")
            else:
                self._log(f"{num_verify_fail}/{self.num_devices} Devices failed verification")
            return num_verify_fail
        return -1
    
    def send_exit_boot(self):
        """Exit bootloader."""
        self._log("Exit bootloader...", end = " ")
        self.send_packet(BOOT_EXIT)
        resp = self.get_response()
        if resp:
            self._log("Done.")
            return True
        return False
       
    def update_firmware(self, firmware_data, do_init = True):
        if len(firmware_data) % 64 != 0:
            padding = 64 - (len(firmware_data) % 64)
            firmware_data += b'\xFF' * padding

        total_blocks = len(firmware_data) // 64
        self._log(f"Flashing {len(firmware_data)} bytes ({total_blocks} blocks)")
        
        start_time = time.perf_counter()
        if do_init:
            if not self.send_init():
                return False
        
        if not self.send_erase_chip():
             return False
        
        for i, offset in enumerate(range(0, len(firmware_data), 64)):
            chunk = firmware_data[offset:offset+64]
            if not self.send_write_sector(offset, chunk):
                return False
            
            # Progress bar
            percent = (i + 1) / total_blocks * 100
            sys.stdout.write(f"\rWriting Block {i+1}/{total_blocks} [{percent:.1f}%]")
            sys.stdout.flush()
        sys.stdout.write(f"\n")

        for i, offset in enumerate(range(0, len(firmware_data), 64)):
            chunk = firmware_data[offset:offset+64]
            if not self.send_verify_sector(offset, chunk):
                return False
            
            # Progress bar
            percent = (i + 1) / total_blocks * 100
            sys.stdout.write(f"\rVerifing Block {i+1}/{total_blocks} [{percent:.1f}%]")
            sys.stdout.flush()
        sys.stdout.write(f"\n")

        if self.send_verify_report() < 0:
            return False
        
        self.send_exit_boot()

        return True

def main():
    parser = argparse.ArgumentParser(description='CH32V003 Bootloader Tool')
    parser.add_argument('--port', '-p', help='COM Port')
    parser.add_argument('--baud', '-b', type=int, default=115200)
    parser.add_argument('-f', '--file', help='Firmware file')    
    parser.add_argument('-v', '--verbosity', type=int, default=0)    
    
    args = parser.parse_args()

    if not args.file:
        print("Error: -f <file> is required")
        return
    
    if not args.port:
        print("Error: -p <port> is required")
        return
    
    loader = CH32V003Bootloader(args.port, args.baud, verbose=args.verbosity)

    try:
        with open(args.file, 'rb') as f:
            print("File loaded.")
            loader.update_firmware(f.read())
    except Exception as e:
        print(f"Upgrade failed.({e})")
        traceback.print_exc()
                
    finally:
        loader.close()
        
if __name__ == "__main__":
    main()
    
    