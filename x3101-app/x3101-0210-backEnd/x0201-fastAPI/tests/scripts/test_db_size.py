from plc_service import plc
for size in [38, 36, 32, 28, 26, 24, 20]:
    data = plc.db_read(1512, 0, size)
    if data:
        print(f"Size {size} works!")
        import struct
        mix_temp = struct.unpack_from('>f', data, 8)[0] if size >= 12 else 0
        mix_weight = struct.unpack_from('>f', data, 12)[0] if size >= 16 else 0
        print(f"  MixTemp: {mix_temp:.2f}, MixWeight: {mix_weight:.2f}")
        break
    else:
        print(f"Size {size} failed")
