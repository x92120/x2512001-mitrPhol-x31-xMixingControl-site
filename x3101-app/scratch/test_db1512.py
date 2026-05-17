import snap7
import struct

def main():
    print("Connecting to S7 PLC at 192.168.21.210...")
    client = snap7.client.Client()
    try:
        client.connect("192.168.21.210", 0, 1)
        if client.get_connected():
            print("Connected successfully!")
            # Read DB1512, size 28 bytes
            data = client.db_read(1512, 0, 28)
            print(f"Raw data: {data.hex()}")
            
            # Parse values
            watchdog = struct.unpack(">h", data[0:2])[0]
            plc_state = struct.unpack(">h", data[2:4])[0]
            current_step = struct.unpack(">h", data[4:6])[0]
            step_timer = struct.unpack(">h", data[6:8])[0]
            mix_temp = struct.unpack(">f", data[8:12])[0]
            mix_weight = struct.unpack(">f", data[12:16])[0]
            agitator_act = struct.unpack(">f", data[16:20])[0]
            highshear_act = struct.unpack(">f", data[20:24])[0]
            hopper_weight = struct.unpack(">f", data[24:28])[0]
            
            print("Parsed DB1512 Telemetry:")
            print(f"  Watchdog: {watchdog}")
            print(f"  PLC State: {plc_state}")
            print(f"  Current Step: {current_step}")
            print(f"  Step Timer: {step_timer}")
            print(f"  Mix Temp: {mix_temp:.2f}")
            print(f"  Mix Weight: {mix_weight:.2f}")
            print(f"  Agitator Act: {agitator_act:.2f}")
            print(f"  HighShear Act: {highshear_act:.2f}")
            print(f"  Hopper Weight: {hopper_weight:.2f}")
        else:
            print("Failed to connect.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
