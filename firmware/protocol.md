## Framing
packets are framed using 7E delimiter and 7D escape code  

## Packet structure
- 1 byte: command
- 1 byte: packet length (including header)
- 2 byte: address / node id
- 0 - 64 byte: data

## Protocol remarks:
- All rx bytes are immediately passed to tx, unless in defered mode
- Commands with bit 7 set to 1 are defered commands. As soon as such command detected, the system enters defered mode essentially blocking passthrough untill the full command is evaluated.  


## Commands
- 0x01: Init upgrade
- 0x02: Chip erase
- 0x03: Write sector
- 0x04: Verify sector
- 0x2B: Exit boot
- 0x85: Report verification

### Init upgrade
- Command: 01 02

### Chip erase
- Command: `02 02`
- Perform a complete chip erase
- Clear verify flag

### Write sector
- Command: `03 44 addr_lo addr_hi data_0 .... data_63`
- Writes 64 byte data sector into flash address 0x8000000 + addr

### Verify sector
- Command: `04 44 addr_lo addr_hi data_0 .... data_63`
- Verify 64 bytes at flash address 0x8000000 + addr matches given data
- Set verify flag if no match

### Report verification
- Command: `85 04 count_lo count_hi`
- Host sends this command with count = 0
- This is a difered command, meaning the receiver does not forward the command to tx until evaluation
- Receiver checks the verify flag, and if set, increment the count indicating faulty update
- After count update receiver forwards the entire command to tx

## Host side operation
- Firmware update sequence
1. Send init command
2. Send chip erase command
3. Send all firmware using write sector commands. Each sector is 64 bytes. Last sector pad with zeros
4. Send verify data commands
5. Send verify result command. Check for returned count. If count is not zero, repeat steps 1-5
6. Send exit boot command
- For each sent command compare the returned packets to the sent ones, they should be identical except for verify result if the count is not zero.


