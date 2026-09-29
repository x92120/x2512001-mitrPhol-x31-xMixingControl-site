import urllib.request
import json
import re

def parse_phase_to_int(phase_str):
    if not phase_str:
        return 0
    digits = re.sub(r'\D', '', phase_str)
    return int(digits) if digits else 0

def clean_action(action_str):
    return int(action_str) if action_str and str(action_str).isdigit() else 0

def main():
    url = "http://localhost:8023/sku-steps/?sku_id=SFCFRU4200"
    
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read().decode())
    except Exception as e:
        print(f"Error fetching data: {e}")
        return
        
    md_content = "# SKU SFCFRU4200 PLC Data Block Table\n\n"
    md_content += "This table matches the exact columns to be sent to the PLC.\n\n"
    
    md_content += "| Phase_ID | Step_id | Action Code | Step_Description | Sap code | Re-code | Amount | Mixing_temperature | Agitator_Speed | High Share | Ph | Brix | Step Time |\n"
    md_content += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    
    for r in data:
        phase_id = parse_phase_to_int(r.get('phase_number', '0'))
        step_id = r.get('sub_step', 0)
        action_code = clean_action(r.get('action_code', '0'))
        step_desc = r.get('action_description', '')
        sap_code = r.get('mat_sap_code', '')
        re_code = r.get('re_code', '')
        amount = r.get('require', 0.0)
        mix_temp = r.get('temperature', 0.0)
        agitator = r.get('agitator_rpm', 0.0)
        high_shear = r.get('high_shear_rpm', 0.0)
        ph = r.get('ph', 7.0) # Default to 7.0 based on earlier observation
        brix = r.get('brix', 0.0)
        step_time = r.get('step_time', 0)
        
        md_content += f"| {phase_id} | {step_id} | {action_code} | {step_desc} | {sap_code} | {re_code} | {amount} | {mix_temp} | {agitator} | {high_shear} | {ph} | {brix} | {step_time} |\n"
        
    artifact_path = '/Users/x92120/xGit/x2512001-mitrPhol-x31-xMixingControl-site/SFCFRU4200_plc_recipe.md'
    
    with open(artifact_path, 'w') as f:
        f.write(md_content)
        
    print(f"Successfully wrote MD file to {artifact_path}")

if __name__ == "__main__":
    main()
