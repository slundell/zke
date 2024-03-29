import serial
import time
import matplotlib.pyplot as plt

baudrate = 9600
# port = "/dev/interceptty"
port = "/dev/ttyUSB0"
# port = "/dev/ttyUSB1"
PKT_START_BYTE = 0xFA
PKT_END_BYTE = 0xF8



stop_pkt = [0xfa, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xf8]
connect_pkt = [0xfa, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x05, 0xf8]
disconnect_pkt = [0xfa, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0xf8]


ser = None

commands = {
    "Stop": 0x02,
    "Connect": 0x05,
    "Disconnect": 0x06,
    "D-CC": 0x01,
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



protocol_nmc_2p4s_100soc = [
    #{"command": "D-CC", "current": 5, "voltage": 12.0, "cutoff_current": .2},
    {"command": "C-CV", "current": 5, "voltage": 16.8, "cutoff_current": .2},
    {"command": "D-CC", "current": 5, "voltage": 12.6, "cutoff_current": .2},
    {"command": "C-CV", "current": 5, "voltage": 16.8, "cutoff_current": .2},
]

protocol = protocol_nmc_2p4s_100soc

log_list = list()
log_filename = "charge.log"
log_commit_last = 0
log_commit_interval = 60

last_pkt = 0


def generate_checksum(buf):
  acc = 0
  for b in buf:
    acc ^= b
  return acc


def decode_volts(b1: int, b2: int):
  return float(b1 * .240 + b2 * .001)


def encode_volts(volts: float):
  volts = volts / 10.
  b1 = int(volts / .240)
  b2 = int((volts - b1 * .240) / .001)
  return (b1, b2)


def encode_current(amps: float, scale: float = 1.):
  amps = amps * scale
  b1 = int(amps / 2.40)
  b2 = int((amps - b1 * 2.40) / .01)
  return (b1, b2)


def decode_amps(b1, b2):
  return float(b1 * 2.40 + b2 * .01)


def decode_mamphours(b1, b2):
  return int((b1 * 240) + b2)



def decode_state(s):


  if s in states.keys():
    return states[s]
  else:
    return "Unknown"


def execute_cmd(cmd):

  cmd_code = commands[cmd["command"]]

  pkt = [0 for _ in range(10)]
  pkt[0] = PKT_START_BYTE
  pkt[1] = cmd_code

  if (cmd["command"] in ["C-CV", "D-CC"]):
    (pkt[2], pkt[3]) = encode_current(cmd["current"])
    (pkt[4], pkt[5]) = encode_volts(cmd["voltage"])
    (pkt[6], pkt[7]) = encode_current(cmd["cutoff_current"])

  elif (cmd["command"] in ["Stop", "Disconnect", "Connect"]):
    pass

  else:
    print(f"Unknown command: {cmd['command']}")
    # TODO: will fail on cmd code lookup above
    return


  pkt[8] = generate_checksum(pkt[1:8])
  pkt[9] = PKT_END_BYTE

  print(f"Executing: {cmd['command']}")
  pretty_print_packet(pkt)


  written = 0
  while (written != 10):
    written = ser.write(pkt)
    print(f"Wrote: {written}")
    ser.flush()

  #for b in pkt:
    #  print(f"0x{b:02x}")
    #  ser.write([b])
    #  ser.flush()
    #  print(ser.in_waiting)
    #  time.sleep(.1)



def read_log(filename):
  global log_list

  print("Reading logfile")
  file = open(filename, "r")
  file.readline()  # skip header

  for line in file.readlines():
    d = line.split(';')
    log_list.append([int(d[0]), str(d[1]), float(d[2]), float(d[3]), int(d[4])])

  # print(log_list)

  file.close()


def log(timestamp, state, voltage, current, mah):
  global log_commit_last, log_commit_interval, log_filename, log_list

  log_list.append([timestamp, state, voltage, current, mah])
  if (log_commit_last + log_commit_interval < timestamp):
    print("Writing logfile")
    file = open(log_filename, "w")
    file.write("# Timestamp; State; Voltage (V), Current (A), Capacity (mAh)\n")
    for line in log_list:
      file.write(f"{int(line[0]):d};{line[1]:s};{line[2]:.03f};{line[3]:.03f};{line[4]:d}\n")
    file.close()
    log_commit_last = timestamp


def pretty_print_packet(pkt):
  if (pkt is None):
    print("[PACKET] <None>")
  else:
    print("[PACKET] " + ' '.join(['0x%02X' % b for b in pkt]) + f" (size: {len(pkt)})")


def pretty_print_state(state, volt, amps, mah):

  if (mah < 3000):
    print(f"{state} {volt:.3f}V {amps:.3f}A {mah:d}mAh")
  else:
    print(f"{state} {volt:.3f}V {amps:.3f}A {mah/1000:d}Ah")


buf = list()


def read_data():
  global buf

  try:
    r = ser.read(19)
    buf += r
  except serial.serialutil.SerialException as e:
    print(e)
    return None


  # if (len(buf) > 0):
    # print("[BUFFER] " + ' '.join(['0x%02X' % b for b in buf]))

  if (PKT_START_BYTE in buf):
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
        return pkt
      else:
        print("CRC mismatch")
        pretty_print_packet(pkt)
        print(f"crc_calc: 0x{crc_calc:02X} crc_read: 0x{crc_read:02X} ")
        return None




def parse_packet(pkt):

  timestamp = time.time()

  if (len(pkt) == 16):
    state = decode_state(pkt[0])
    if (state in ["Done", "Idle", "C-CV", "D-CC", ]):
      amps = decode_amps(pkt[1], pkt[2])
      volt = decode_volts(pkt[3], pkt[4])
      mah = decode_mamphours(pkt[5], pkt[6])

      return (timestamp, state, volt, amps, mah)

    #elif (state == "Done"):
    #  pretty_print_packet(pkt)
    #  print("Done")
    #  return None

    else:
      print(f"Unknown state: {state}")
      pretty_print_packet(pkt)
      return None
  else:
    print(f"Unexpected package size: {len(pkt):d}")
    pretty_print_packet(pkt)
    return None


def is_connected():
  global last_pkt
  return (ser is not None) and (last_pkt + 20 > time.time())


def disconnect():
  global ser

  if ser is None:
    return

  execute_cmd({"command": "Disconnect"})
  ser.close()
  ser = None



def connect():
  global ser, last_pkt


  print(f"Connecting to {port}")
  try:
    if ser is not None:
      ser.close()

    ser = serial.Serial(port, baudrate, timeout=5)

  except serial.SerialException as e:
    print(e)
    ser = None
    return

  # print("Listening for activity")

  #b = ser.read()
  #pretty_print_packet(b)


  b = None
  while (b is None or len(b) == 0):
    execute_cmd({"command": "Connect"})
    try:
      b = ser.read()
    except serial.SerialException as e:
      print(e)

    pretty_print_packet(b)
  print("Connected")


  #b = None

  #while (b is None or len(b) == 0):
   # execute_cmd({"command": "Connect"})
  #execute_cmd({"command": "Stop"})
    #for i in range(0xFF):
      #ser.write([0xfa, i, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, i, 0xf8])


    #try:
  #b = ser.read()
      #print(b)
      #pretty_print_packet(b)
    #except serial.SerialException as e:
     # print(e)
      #continue

  #pretty_print_packet(b)

  execute_cmd({"command": "C-CV", "current": 5, "voltage": 16.8, "cutoff_current": .2})

  # execute_cmd({"command": "Stop"})


  #print("Waiting for valid data")

  #pkt = read_data()
  #while (pkt is None):
  #  pretty_print_packet(pkt)
  #  pkt = read_data()

  #pretty_print_packet(pkt)
  #(last_pkt, _, _, _, _) = parse_packet(pkt)



def reconnect():
  disconnect()
  connect()


def print_port_status():
  # print(ser)
  print("Port status:", end='')
  print(" BREAK: " + ("ON" if ser.break_condition else "OFF"), end='')
  print("  RTS: " + ("ON" if ser.rts else "OFF"), end='')
  print("  DTR: " + ("ON" if ser.dtr else "OFF"), end='')
  # print("  CTS: " + ("ON" if ser.cts else "OFF"), end='')
  # print("  RI: " + ("ON" if ser.ri else "OFF"), end='')
  # print("  CD: " + ("ON" if ser.cd else "OFF"), end='')
  print()


def generate_report(log):

   curr_state = None
   state_start_time = None
   timestamps = list()
   voltages = list()
   currents = list()
   capacities = list()

   for line in log:
     (timestamp, state, voltage, current, capacity) = line

     if state != curr_state:
       if curr_state in ['C-CV', 'D-CC', 'D-CP']:
         #  render
         pass

       timestamps = list()
       voltage = list()
       current = list()
       capacity = list()
       curr_state = state
       state_start_time = timestamp


     timestamps.append(timestamp - state_start_time)
     voltages.append(voltage)
     currents.append(current)
     capacities.append(capacity)





#   plt.plot



def main():
  global protocol, last_pkt
  protocol_idx = 0
  protocol_idx_next = 0

  repeat = 0
  state = "Idle"
  last_pkt = 0

  connect()

  read_log("charge.log")
  generate_report(log_list)

  command_accepted = False
  while protocol_idx < len(protocol):

    if not is_connected():
      connect()

    pkt = read_data()

    if (pkt is not None):
      last_pkt = time.time()
      print_port_status()

      p = parse_packet(pkt)
      if (p is not None):

        (timestamp, state, voltage, current, capacity) = p

        # pretty_print_packet(pkt)
        pretty_print_state(state, voltage, current, capacity)

        # print(f"Repeat: {repeat}")


        if repeat < 5 and not command_accepted:
          execute_cmd(protocol[protocol_idx])
          repeat += 1
        else:
          if (state in ["Done"]):
            protocol_idx = protocol_idx_next

          if (state != protocol[protocol_idx]["command"]):
            command_accepted = False
            if (repeat < 10):
              if (repeat > 3):
                execute_cmd({"command": "Stop"})
              execute_cmd(protocol[protocol_idx])
              repeat += 1
            else:
              connect()
              repeat = 0
          else:
            repeat = 0
            command_accepted = True
            protocol_idx_next = protocol_idx + 1

      log(timestamp, state, voltage, current, capacity)


      last_pkt = time.time()

    time.sleep(.01)  # be nice





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



# Issues

  # # Connection lock-ups
    Sometimes the device does not respond to connection attempts. Niether on ttyUSB0 and interceptty. If EB.exe is used through wine to connect+disconnect on interceptty and then connect on ttyUSB0 then the device becomes responsive again. Maybe some RTC/CTS? ser.close()?


[RX]  .... etc  0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x00 0xf8

[TX]  0xfa 0x05 0x00 0x00 0x00 0x00 0x00 0x00 0x05 0xf8 [Connect packet]
Mine  0xFA 0x05 0x00 0x00 0x00 0x00 0x00 0x00 0x05 0xF8

[RX]  0xfa 0x07 0x00 0x00 0x45 0x62 0x00 0x23 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x00 0xf8 [Idle]
[RX]  0xfa 0x07 0x00 0x00 0x45 0x62 0x00 0x23 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x00 0xf8 [Idle]
[RX]  0xfa 0x07 0x00 0x00 0x45 0x62 0x00 0x23 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x00 0xf8 [Idle]
[RX]  0xfa 0x07 0x00 0x00 0x45 0x62 0x00 0x23 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x00 0xf8 [Idle]
[RX]  0xfa 0x07 0x00 0x00 0x45 0x62 0x00 0x23 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x00 0xf8 [Idle]
[RX]  0xfa 0x07 0x00 0x00 0x45 0x62 0x00 0x23 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x00 0xf8 [Idle]
[RX]  0xfa 0x07 0x00 0x00 0x45 0x62 0x00 0x23 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x00 0xf8 [Idle]
[RX]  0xfa 0x07 0x00 0x00 0x45 0x62 0x00 0x23 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x00 0xf8 [Idle]

[TX]  0xfa 0x71 0x02 0x14 0x07 0x00 0x00 0x14 0x74 0xf8 [C-CV cmd]

[RX]  0xfa 0x11 0x00 0x00 0x45 0x62 0x00 0x00 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x35 0xf8 [C-CV]
[RX]  0xfa 0x11 0x02 0x14 0x45 0x66 0x00 0x01 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x26 0xf8 [C-CV]
[RX]  0xfa 0x11 0x02 0x14 0x45 0x69 0x00 0x04 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x2c 0xf8 [C-CV]
[RX]  0xfa 0x11 0x02 0x14 0x45 0x69 0x00 0x07 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x2f 0xf8 [C-CV]
[RX]  0xfa 0x11 0x02 0x14 0x45 0x6d 0x00 0x0a 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x26 0xf8 [C-CV]
[RX]  0xfa 0x11 0x02 0x14 0x45 0x6d 0x00 0x0c 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x20 0xf8 [C-CV]
[RX]  0xfa 0x11 0x02 0x14 0x45 0x6d 0x00 0x0f 0x00 0x00 0x02 0x14 0x07 0x00 0x00 0x14 0x06 0x23 0xf8 [C-CV]

[TX]  0xfa 0x02 0x00 0x00 0x00 0x00 0x00 0x00 0x02 0xf8 [Stop]
[TX]  0xfa 0x06 0x00 0x00 0x00 0x00 0x00 0x00 0x06 0xf8 [Disconnect]


Prettying wireshark captures
 grep --no-filename --before=35 "usb\.capdata" *.json | grep "src\|capdata" | sed "s/\"usb\.src\": \"host\",/host -> dev/" | sed "s/\"usb\.src\": \"1\.52\.[0-9]\",/host <- dev/" | sed "s/\"usb\.capdata\": //" | tr -s '\n' '#'| sed "s/\"#/\n/g" | tr -d '#"'


"""

if __name__ == "__main__":
  main()


















