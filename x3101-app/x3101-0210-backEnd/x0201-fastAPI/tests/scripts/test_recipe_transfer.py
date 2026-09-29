import sys
import os
import logging

logging.basicConfig(level=logging.DEBUG)

# Ensure the script can import plc_service
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from plc_service import write_full_recipe_to_plc, plc, DB_FULL_RECIPE, unpack_s7_string
import struct

def main():
    print("Testing recipe transfer to DB1511...")
    
    batch_id = "BATCH-2026-TEST-001"
    sku_id = "SKU-MIX-999"
    
    steps = [
        {
            "seq": 1,
            "phase_no": 10,
            "sub_step": 1,
            "action_code": "FILL_WTR",
            "phase_id": "P01",
            "re_code": "MAT-WATER-001",
            "target_weight": 500.0,
            "temp_sp": 0.0,
            "temp_low": 0.0,
            "temp_high": 0.0,
            "agitator_sp": 0.0,
            "highshear_sp": 0.0,
            "step_time": 0
        }
    ]
    
    success = write_full_recipe_to_plc(batch_id, sku_id, steps)
    if success:
        print("✅ Successfully wrote recipe to DB1511.")
    else:
        print("❌ Failed to write recipe to DB1511.")

if __name__ == "__main__":
    main()
