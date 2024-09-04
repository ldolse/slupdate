

def create_combined_image_and_cue(cue, base_name, combined_image_path):
    # Export Cue
    cue.export_cue(os.path.join("CCD", base_name, f"{base_name}.cue"), f"{base_name}.img")
    print("Done writing CUE!")

    # Create Subchannel
    subchannel_filename = os.path.join("CCD", base_name, f"{base_name}.sub")
    create_sub_channel(subchannel_filename, cue.multi_sector_count)

    # Patch Subchannel with LSD if exists
    lsd_path = os.path.join(cue.bin_path, f"{base_name}.lsd")
    if os.path.exists(lsd_path):
        print(f"LibCrypt patch '{base_name}.lsd' was found! Patching subchannel...")
        with open(subchannel_filename, "rb+") as sub_file:
            sub_data = bytearray(sub_file.read())
            lsd_to_sub(lsd_path, sub_data)
            sub_file.seek(0)
            sub_file.write(sub_data)
        print("Finished LSD -> Patching!")
    else:
        print(f"Could not find '{lsd_path}'! Skipping...")
        
