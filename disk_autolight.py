#!/usr/bin/python3
import subprocess
import re
import platform

def run_command(command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
    if result.returncode != 0:
        print(f"Error running command: {command}\nError message: {result.stderr}")
    return result.stdout


def get_disk_info_from_smartctl(disk_path):
    smartctl_output = run_command(f'smartctl -i {disk_path}')
    serial_number_match = re.search(r'Serial Number:\s+(\S+)', smartctl_output)
    model_number_match = re.search(r'(?:Device Model|Product):\s+(.+)', smartctl_output)
    if serial_number_match and model_number_match:
        return serial_number_match.group(1), model_number_match.group(1)
    return None, None

def get_disk_serial(disk_path):
    if platform.system() == 'Linux':
        return get_disk_info_from_smartctl(disk_path)[0]
    elif platform.system() == 'FreeBSD':
        return run_command(f'diskinfo -s {disk_path}').replace("\n","")
    else:
        raise Exception(f"Unsupported platform {platform.system()}")

def get_unhealthy_disks():
    zpool_status_output = run_command('zpool list -PLvH')
    unhealthy_disks = []
    if platform.system() == 'FreeBSD':
        glabel_output = run_command('glabel status')
        glabels = {}
        glabel_output = glabel_output.split("\n")
        for glabel_output in glabel_output:
            glabel_output = re.sub(' +', ' ', glabel_output)
            if len(glabel_output.split(" ")) != 3:
                continue
            name,ststus,compones = glabel_output.split(" ")
            glabels[name]=compones
    for zpool_status_line in zpool_status_output.split("\n"):
        if zpool_status_line == "":
            continue
        if zpool_status_line[0] != "\t":
            continue
        if not zpool_status_line.startswith("\t/dev"):
            continue
        zpool_status_line = zpool_status_line.split("\t")
        disk_path = zpool_status_line[1]
        disk_health = zpool_status_line[10]
        

        if platform.system() == 'Linux' and disk_path.startswith("/dev/disk/by-partuuid"):
            # Reverse lookup real disk path
            # But smartctl in linux supports lookup disk info by partid
            pass
        elif platform.system() == 'FreeBSD':
            # Reverse lookup real disk path
            label_name = disk_path[5:]
            if disk_path.startswith("/dev/gptid"):
                if label_name in glabels:
                    compones = glabels[label_name]
                    label_name = compones
                    disk_path = "/dev/" + compones
                else:
                    label_name=""
                    print(label_name + " not in " + str(glabels.keys()))
            if ("p" in label_name) and label_name.rsplit("p")[1].isnumeric():
                label_name = label_name.rsplit("p")[0]
                #print(f"Remove partid from {disk_path} to {label_name}")
                disk_path = "/dev/" + label_name
            else:
                print(f"Not able to remove partid from {disk_path}")

        if disk_health != "ONLINE":
            unhealthy_disks += [disk_path]
        print(f"Found disks: {disk_path} SN={get_disk_serial(disk_path)} ,status {disk_health}")
        
    return unhealthy_disks

def get_disk_info_from_storcli():
    storcli_output = run_command('storcli /cALL/eALL/sALL show all')
    disks = re.findall(r'/c(\d+)/e(\d+)/s(\d+).+?SN = (\S+).+?Model Number = ([^\n]*).+?Inquiry Data =', storcli_output, re.DOTALL)
    return disks

def light_up_disk(controller_id, enclosure_id, slot_id, serial_number, model_number):
    command = f'storcli /c{controller_id}/e{enclosure_id}/s{slot_id} start locate'
    run_command(command)
    print(f"Set locate LED ON at controller {controller_id} enclosure {enclosure_id}, slot {slot_id} for SN={serial_number}, Model={model_number}")

def light_off_disk(controller_id, enclosure_id, slot_id, serial_number, model_number):
    command = f'storcli /c{controller_id}/e{enclosure_id}/s{slot_id} stop locate'
    run_command(command)
    print(f"Set locate LED OFF at controller {controller_id} enclosure {enclosure_id}, slot {slot_id} for SN={serial_number}, Model={model_number}")

def main():
    unhealthy_disks = get_unhealthy_disks()
    unhealthy_serial_model_pairs = set()
    if len(unhealthy_disks) > 0:
        print("Found unhealthy disks:",unhealthy_disks)
    else:
        print("All disk healthy")
    for disk in unhealthy_disks:
        serial_number, model_number = get_disk_info_from_smartctl(disk)
        if serial_number and model_number:
            unhealthy_serial_model_pairs.add((serial_number, model_number))
    disks_info = get_disk_info_from_storcli()
    for controller_id, enclosure_id, slot_id, serial_number, model_number in disks_info:
        if (serial_number, model_number) in unhealthy_serial_model_pairs:
            light_up_disk(controller_id, enclosure_id, slot_id, serial_number, model_number)
        else:
            light_off_disk(controller_id, enclosure_id, slot_id, serial_number, model_number)

if __name__ == "__main__":
    main()
