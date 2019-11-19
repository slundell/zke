import serial
import time

baudrate = 9600
port = "/dev/interceptty"
# port = "/dev/ttyUSB0"
PKT_START_BYTE = 0xFA
PKT_END_BYTE = 0xF8
PKT_SMALLEST = 10


stop_pkt_1 = [0xfa, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xf8]
#stop_pkt_2 = [0xfa, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0xf8]
connect_pkt = [0xfa, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x05, 0xf8]
disconnect_pkt = [0xfa, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0xf8]


ser = serial.Serial(port, baudrate, timeout=5)

commands = {
    "D-CC": 0x01,
    "Stop": 0x02,
    "Connect": 0x05,
    "Disconnect": 0x06,
    "D-CP": 0x11,
    "C-NiMh": 0x21,
    "C-NiCd": 0x31,
    "C-LiPo": 0x41,
    "C-LiFe": 0x51,
    "C-Pb": 0x61,
    "C-CV": 0x71,
}

states = {
    0x00: "Done",
    0x06: "Idle",
    0x07: "Idle",
    0x0A: "D-CC",
    0x0B: "D-CP",
    0x0C: "C-NiMh",
    0x0D: "C-NiCd",
    0x0E: "C-LiPo",
    0x0F: "C-LiFe",
    0x10: "C-Pb",
    0x11: "C-CV",
    0x1B: "Done"
}



protocol = list()
# protocol.append({"command": "Disconnect"})
# protocol.append({"command": "Connect"})

protocol.append({"command": "Stop"})

protocol.append(
    {
        # C-CV 0.1A 2.4V 0.05A cutoff
        "command": "C-CV",
        "current": 5,
        "voltage": 16.8,
        "cutoff_current": .1
    }
)

protocol.append(
    {
        "command": "D-CC",
        "current": 5,
        "voltage": 12,
        "cutoff_current": 0.1
    }
)
protocol.append(
    {
        # C-CV 0.1A 2.4V 0.05A cutoff
        "command": "C-CV",
        "current": 5,
        "voltage": 16.8,
        "cutoff_current": .1
    }
)

# protocol = [{"command": i} for i in range(0xFF)]


def generate_checksum(buf):
  acc = 0
  for b in buf:
    acc ^= b
  return acc


def decode_volts(b1: int, b2: int):
  # b1 = int(pkt[3])
  # b2 = int(pkt[4])
  # print(f"0x{b1:02X} 0x{b2:02X}")
  return float(b1 * .240 + b2 * .001)


def encode_volts(volts: float):
  volts = volts / 10.
  b1 = int(volts / .240)
  b2 = int((volts - b1 * .240) / .001)

  print(f"0x{b1:02X} 0x{b2:02X}")
  return (b1, b2)


def encode_current(amps: float, scale: float = 1.):
  amps = amps * scale

  b1 = int(amps / 2.40)
  b2 = int((amps - b1 * 2.40) / .01)

  print(f"0x{b1:02X} 0x{b2:02X}")
  return (b1, b2)



def decode_amps(b1, b2):
  # b1 = int(pkt[1])
  # b2 = int(pkt[2])
  return float(b1 * 2.40 + b2 * .01)


def decode_mamphours(b1, b2):
  # b1 = int(pkt[1])
  # b2 = int(pkt[2])
  # print(f"0x{b1:02X} 0x{b2:02X}")
  return int((b1 * 240) + b2)



def decode_state(s):


  if s in states.keys():
    return states[s]
  else:
    return "Unknown"


def execute_cmd(cmd):
  print(cmd)
  cmd_code = commands[cmd["command"]]

  pkt = [0 for _ in range(10)]
  pkt[0] = PKT_START_BYTE
  pkt[1] = cmd_code

  if (cmd["command"] == "C-CV"):
    (c1, c2) = encode_current(cmd["current"])
    (v1, v2) = encode_volts(cmd["voltage"])
    (o1, o2) = encode_current(cmd["cutoff_current"])

    pkt[2] = c1
    pkt[3] = c2
    pkt[4] = v1
    pkt[5] = v2
    pkt[6] = o1
    pkt[7] = o2

  if (cmd["command"] == "D-CC"):
    (c1, c2) = encode_current(cmd["current"])
    (v1, v2) = encode_volts(cmd["voltage"])
    (o1, o2) = encode_current(cmd["cutoff_current"])

    pkt[2] = c1
    pkt[3] = c2
    pkt[4] = v1
    pkt[5] = v2
    pkt[6] = o1
    pkt[7] = o2

  else:
    pass

  pkt[8] = generate_checksum(pkt[1:8])
  pkt[9] = PKT_END_BYTE


  # print(f"Executing command: {cmd['command']}")
  print("[>] " + ' '.join(['0x%02X' % b for b in pkt]))

  written = ser.write(pkt)
  ser.flush()
  print(f"Written: {written}")

  if (written != 10):
    print(f"Wrote {written} bytes")


def main():
  protocol_idx = 0
  wait = 0
  state = "Idle"
  buf = list()
  #  ser.write(disconnect_pkt)
  #  ser.write(connect_pkt)
  execute_cmd(protocol[0])

  while protocol_idx < len(protocol):

    if ser.in_waiting > 0:

      try:
        r = ser.read(19)
        buf += r
      except serial.serialutil.SerialException as e:
        print(e)


      # if (len(buf) > 0):
        # print("[BUFFER] " + ' '.join(['0x%02X' % b for b in buf]))

      if (PKT_START_BYTE in buf):
        wait += 1

        start = buf.index(PKT_START_BYTE)
        buf = buf[start:]

        if (PKT_END_BYTE in buf):

          end = buf.index(PKT_END_BYTE)
          start = len(buf[end::-1]) - 1 - buf[end::-1].index(PKT_START_BYTE)


          crc_read = buf[end - 1]
          pkt = buf[start + 1:end - 1]
          buf = buf[end + 1:]



          crc_calc = generate_checksum(pkt)

          if (crc_calc == crc_read):

            if (len(pkt) == 16):
              state = decode_state(pkt[0])
              if (state in ["Idle", "C-CV", "D-CC", ]):
                amps = decode_amps(pkt[1], pkt[2])
                volt = decode_volts(pkt[3], pkt[4])
                mah = decode_mamphours(pkt[5], pkt[6])

                print(f"{state} {volt:.3f}V {amps:.3f}A {mah:d}mAh")

              elif (state == "Done"):
                print("Done")

              else:
                print(f"Unknown state: {state}")
                print("[PACKET] " + ' '.join(['0x%02X' % b for b in pkt]))
            else:
              print(f"Unexpected package size: {len(pkt):d}")
              print("[PACKET] " + ' '.join(['0x%02X' % b for b in pkt]))
          else:
            print("CRC mismatch")
            print("[PACKET] " + ' '.join(['0x%02X' % b for b in pkt]))
            print(f"crc_calc: 0x{crc_calc:02X} crc_read: 0x{crc_read:02X} ")
    else:
      time.sleep(.01)


    if ((wait >= 2) and ((state == "Idle") or (state == "Done"))):

      protocol_idx += 1

      if (protocol_idx >= len(protocol)):
        break
      execute_cmd(protocol[protocol_idx])
      wait = 0





"""

# Monitor packets

[<] 0xFA 0x11 0x01 0xDA 0x42 0x04 0x09 0x47 0x00 0x00 0x01 0xDB 0x07 0x00 0x00 0x0C 0x06 0x15 0xF8


  b00: 0xFA   start byte
  b01: 0x11   State
  b02: 0x01   Amps MSB
  b03: 0xDA   Amps LSB
  b04: 0x42   Volts MSB
  b05: 0x04   Volts LSB
  b06: 0x09   mAh MSB
  b07: 0x47   mAh LSB
  b08: 0x00
  b09: 0x00
  b10: 0x01
  b11: 0xDB
  b12: 0x07
  b13: 0x00
  b14: 0x00
  b15: 0x0C
  b16: 0x06
  b17: 0x15   crc
  b18: 0xF8   end byte


  State:
    0x00: Done?
    0x07: Idle
    0x0A: D-CC
    0x0B: D-CP
    0x0C: C-NiMh
    0x0D: C-NiCd
    0x0E: C-LiPo
    0x0F: C-LiFe
    0x10: C-Pb
    0x11: C-CV



  Amp conversion

  1.0A
  [<] 0xFA 0x11 0x00 0x64 0x43 0xCC 0x00 0x31 0x00 0x00 0x00 0x64 0x07 0x00 0x00 0x1E 0x06 0xB0 0xF8
  Amps: 0x00 (0)  0x64 (100) = 100

  2.0A
  [<] 0xFA 0x11 0x00 0xC8 0x43 0xD7 0x00 0x06 0x00 0x00 0x00 0xC8 0x07 0x00 0x00 0x1E 0x06 0x9C 0xF8
  Amps: 0x00 (0)  0xC8 (200) = 200

  2.1A
  [<] 0xFA 0x11 0x00 0xD2 0x43 0xE5 0x00 0x0B 0x00 0x00 0x00 0xD2 0x07 0x00 0x00 0x1E 0x06 0xA3 0xF8
  Amps: 0x00 (0)  0xD2 (210) = 210

  2.3A
  [<] 0xFA 0x11 0x00 0xE6 0x44 0x12 0x00 0x07 0x00 0x00 0x00 0xE6 0x07 0x00 0x00 0x1E 0x06 0x5F 0xF8
  Amps: 0x00 (0)  0xE6 (230) = 230

  2.39A
  [<] 0xFA 0x11 0x00 0xEF 0x44 0x12 0x00 0x07 0x00 0x00 0x00 0xEF 0x07 0x00 0x00 0x1E 0x06 0x5F 0xF8
  Amps: 0x00 (0)  0xEF (239) = 239

  2.4A
  [<] 0xFA 0x11 0x01 0x00 0x43 0xE9 0x00 0x07 0x00 0x00 0x01 0x00 0x07 0x00 0x00 0x1E 0x06 0xA3 0xF8
  Amps: 0x01 (1)  0x00 (0) = 256

  2.5A
  [<] 0xFA 0x11 0x01 0x0A 0x43 0xE9 0x00 0x0C 0x00 0x00 0x01 0x0A 0x07 0x00 0x00 0x1E 0x06 0xA8 0xF8
  Amps: 0x01 (1)  0x0A (10) = 266

  3.0A
  [<] 0xFA 0x11 0x01 0x3C 0x43 0xE9 0x00 0x17 0x00 0x00 0x01 0x3C 0x07 0x00 0x00 0x1E 0x06 0xB3 0xF8
  Amps: 0x01 (1)  0x3C (60) = 316

  5.0A
  [<] 0xFA 0x11 0x02 0x14 0x44 0x30 0x00 0x0D 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x1E 0x06 0x77 0xF8
  Amps: 0x02 (2)  0x14 (20) = 532




# Command Packets


# # Command coding

  Disconnect
  [>] 0xfa (0x06) 0x00 0x00 0x00 0x00 0x00 0x00 0x06 0xf8

  D-CC 0.05A 0.00V 0min
  [>] 0xfa (0x01) 0x00 0x05 0x00 0x00 0x00 0x00 0x04 0xf8

  D-CP 1W 0.00V 0min
  [>] 0xfa (0x11) 0x00 0x01 0x00 0x00 0x00 0x00 0x10 0xf8

  C-NiMh 0.05A 0 Cells 0 min
  [>] 0xfa (0x21) 0x00 0x05 0x00 0x00 0x00 0x00 0x24 0xf8

  C-NiCd 0.05A 0 Cells 0 min
  [>] 0xfa (0x31) 0x00 0x05 0x00 0x00 0x00 0x00 0x34 0xf8

  C-LiPo 0.05A 0 Cells 0 min
  [>] 0xfa (0x41) 0x00 0x05 0x00 0x00 0x00 0x00 0x44 0xf8

  C-LiFe 0.05A 0 Cells 0 min
  [>] 0xfa (0x51) 0x00 0x05 0x00 0x00 0x00 0x00 0x54 0xf8

  C-Pb 0.05A 0 Cells 0 min
  [>] 0xfa (0x61) 0x00 0x05 0x00 0x00 0x00 0x00 0x64 0xf8

  C-CV 0.05A 0.00V 0.00A
  [>] 0xfa (0x71) 0x00 0x05 0x00 0x00 0x00 0x00 0x74 0xf8




# # Amp coding
  Same as when reading

  C-CV 0.1A 16.8V 0.05A cutoff
  [>] 0xfa 0x71 (0x00 0x0a) 0x07 0x00 0x00 0x05 0x79 0xf8

  C-CV 1A 16.8V 0.05A cutoff
  [>] 0xfa 0x71 (0x00 0x64) 0x07 0x00 0x00 0x05 0x17 0xf8

  C-CV 2A 16.8V 0.05A cutoff
  [>] 0xfa 0x71 (0x00 0xc8) 0x07 0x00 0x00 0x05 0xbb 0xf8

  C-CV 3A 16.8V 0.05A cutoff
  [>] 0xfa 0x71 (0x01 0x3c) 0x07 0x00 0x00 0x05 0x4e 0xf8

  C-CV 4A 16.8V 0.05A cutoff
  [>] 0xfa 0x71 (0x01 0xa0) 0x07 0x00 0x00 0x05 0xd2 0xf8




# # Volt coding
  Same as when reading but * .1

  C-CV 0.1A 2.4V 0.05A cutoff
  [>] 0xfa 0x71 0x00 0x0a (0x01 0x00) 0x00 0x05 0x7f 0xf8

  C-CV 0.1A 9.975V 0.05A cutoff
  [>] 0xfa 0x71 0x00 0x0a (0x04 0x25) 0x00 0x05 0x5f 0xf8

  C-CV 0.1A 10.0V 0.05A cutoff
  [>] 0xfa 0x71 0x00 0x0a (0x04 0x28) 0x00 0x05 0x52 0xf8

  C-CV 0.1A 16.8V 0.05A cutoff
  [>] 0xfa 0x71 0x00 0x0a (0x07 0x00) 0x00 0x05 0x79 0xf8


  [>] 0xFA 0x71 0x02 0x14 (0x46 0x00) 0x00 0x05 0x24 0xF8






# # Auto test
 [>] 0xfa 0x01 0x00 0x0a 0x00 0x50 0x00 0x00 0x5b 0xf8 0xfa 0x07 0x00 0x0a 0x00 0x50 0x00 0x00 0x5d 0xf8

"""

if __name__ == "__main__":
  main()
