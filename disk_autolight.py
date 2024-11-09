#!/usr/bin/python3
import subprocess
import re
import platform

def run_command(command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
    if result.returncode != 0:
        print(f"Error running command: {command}\nError message: {result.stderr}")
    return result.stdout


def get_disk_info_from_smartctl(disk):
    smartctl_output = run_command(f'smartctl -i {disk}')
    serial_number_match = re.search(r'Serial Number:\s+(\S+)', smartctl_output)
    model_number_match = re.search(r'(?:Device Model|Product):\s+(.+)', smartctl_output)

    if serial_number_match and model_number_match:
        return serial_number_match.group(1), model_number_match.group(1)
    return None, None

def get_unhealthy_disks():
    zpool_status_output = run_command('zpool list -PLvH')
    unhealthy_disks = []
    for zpool_status_line in zpool_status_output:
        zpool_title = ""
        if zpool_status_line == "":
            continue
        if zpool_status_line[0] != "\t":
            continue
        if not zpool_status_line.startswith("/dev"):
            continue
        zpool_status_line = zpool_status_line.split("\t")
        disk_path = zpool_status_line[1]
        disk_health = zpool_status_line[10]
        if disk_health != "ONLINE":
            print(f"Found unhealthy disks: {disk_path} ,status {disk_health}")
        if platform.system() == 'Linux' and disk_path.startswith("/dev/disk/by-partuuid"):
            # Reverse lookup real disk path
            # But smartctl in linux supports lookup disk info by partid
            pass
        elif platform.system() == 'FreeBSD' and disk_path.startswith("/dev/gptid"):
            # Reverse lookup real disk path
            label_name = disk_path[5:]
            glabel_output = run_command('glabel status')
            glabel_output = glabel_output.split("\n")
            for glabel_output in glabel_output:
                if glabel_output == "":
                    continue
                name,ststus,compones = glabel_output.split("\t")
                if label_name == name:
                    if compones.rsplit("p")[1].isnumeric():
                        disk_part = compones.rsplit("p")[0]
                    disk_path = "/dev/" + disk_part
        unhealthy_disks += [disk_path]
    return unhealthy_disks




def get_disk_info_from_storcli():
    storcli_output = run_command('storcli /c0/eALL/sALL show all')
    disks = re.findall(r'/c0/e(\d+)/s(\d+).+?SN = (\S+).+?Model Number = (.+?)(?:\s|$)', storcli_output, re.DOTALL)
    return disks

def light_up_disk(enclosure_id, slot_id):
    command = f'storcli /c0/e{enclosure_id}/s{slot_id} start locate'
    run_command(command)
    print(f"Started locate LED for enclosure {enclosure_id}, slot {slot_id}")

def light_off_disk(enclosure_id, slot_id):
    command = f'storcli /c0/e{enclosure_id}/s{slot_id} stop locate'
    run_command(command)
    print(f"Stopped locate LED for enclosure {enclosure_id}, slot {slot_id}")

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

    for enclosure_id, slot_id, serial_number, model_number in disks_info:
        if (serial_number, model_number) in unhealthy_serial_model_pairs:
            light_up_disk(enclosure_id, slot_id)
        else:
            light_off_disk(enclosure_id, slot_id)

if __name__ == "__main__":
    main()
