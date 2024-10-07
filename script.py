try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

import pycdlib
import argparse
import requests
import collections
import re
import os



parser = argparse.ArgumentParser(description="A simple Ubuntu Server autoinstall script.")
parser.add_argument("-i", "--iso", type=str, help="The path to the original ISO image. (If none provided - downloaded from releases.ubuntu.com)")
parser.add_argument("-v", "--version", type=str, help="The version of Ubuntu Server you want to download. (Default - 22.04)")
parser.add_argument("-o", "--output", type=str, help="The desired path to the output image. (If none provided - outputs to the working directory)")
parser.add_argument("-c", "--config", type=str, help="The path to the user-data config file. (If none provided - will be generated)")
parser.add_argument("-s", "--ssh", type=str, help="The path to the public ssh key you want to include in the custom image. (Default - None)")
parser.add_argument("-t", "--time", default=10, type=str, help="The timeout you want to assign to the bootloader. (Default - 10)")
args = parser.parse_args()

GRUB_CONFIG = "grub.cfg"

def get_output_path():
    # Output path check
    if args.output:
        output_dir = os.path.dirname(args.output)

        if(os.path.exists(output_dir) and args.output.endswith(".iso") or os.path.exists(args.output)):
            print(f"Using provided output path: {args.output}")
        else:
            print(f"Output path not found: {args.output}")
            exit(1)
    else:
        print("No output path provided. Using current script directory.")
        args.output = os.path.dirname(os.path.realpath(__file__))
        print(f"Using output path: {args.output}")

def get_iso():
    if args.iso:
        if(os.path.exists(args.iso)):
            print(f"Using provided ISO: {args.iso}")
        else:
            print(f"ISO not found: {args.iso}")
            exit(1)
    else:
        print("No ISO path provided. Checking for existing ISOs in script directory...")
        if check_for_iso(os.path.dirname(os.path.realpath(__file__))) is not None:
            print("Using found ISO.")
        else:
            print("No already existing local ISOs found. Checking for given remote ISO version...")
            # Remote .ISO file version validity check/assignment
            if args.version:
                download_iso(args.version, args.output)
            else:
                print("No version provided. Defaulting to 22.04.")
                args.version = "22.04"
                download_iso(args.version, args.output)
                
def check_for_iso(directory):
    # Checks if there are any ISOs in the script's directory
    for filename in os.listdir(directory):
        if "ubuntu" in filename and filename.endswith(".iso"):
            print(f"Found already existing ISO: {filename}")
            answer = input("Do you want to use this ISO? (Y/N): ")
            if answer == "y" or answer == "Y":
                args.iso = os.path.join(directory, filename)
                return args.iso
            else:
                continue
    return None

def download_iso(version, output_directory):
    url = f"https://releases.ubuntu.com/{version}/"
    response = requests.get(url)
    response.raise_for_status()

    match = re.search(r'href="(ubuntu-.*-server.*\.iso)"', response.text)
    if match:
        iso_url = url + match.group(1)
    else:
        print("Given ISO version could not be found.")
        exit(1)

    file_name = os.path.basename(iso_url)

    # Downloads the named ISO file
    print(f"Downloading Ubuntu Server {version} ISO from {iso_url}...")
    os.chdir(output_directory)
    with requests.get(iso_url, stream=True) as r:
        r.raise_for_status()
        with open(file_name, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print(f"Download complete: {file_name}")
    args.iso = os.path.join(output_directory, file_name)

def clone_data():
    # Clones data from provided user-data file (if provided)
    f = open(args.config, "r")
    config = f.read()
    f.close()

    f = open("user-data", "w")
    f.write(config)
    f.close()

    f = open("meta-data", "w")
    f.close()
    

def edit_iso():
    # ISO editing function
    iso = pycdlib.PyCdlib()
    iso.open(args.iso)
    
    iso.add_directory("/SERVER", rr_name='server')
    iso.add_file("user-data", "/SERVER/USER_DATA;1", rr_name='user-data')
    iso.add_file("meta-data", "/SERVER/META_DATA;1", rr_name='meta-data')
    print("Added server files")
    
    iso.rm_file("/BOOT/GRUB/GRUB.CFG;1", rr_name='grub.cfg')
    iso.add_file(GRUB_CONFIG, "/BOOT/GRUB/GRUB.CFG;1", rr_name='grub.cfg')
    iso.add_eltorito('/BOOT/GRUB/GRUB.CFG;1')
    print("Edited grub")
    
    iso.write(args.output + "/output.iso")

    iso.close()


def get_config():
    # User-data config file check
    if args.config:
        if(os.path.exists(args.config)):
            clone_data()
            print(f"Using provided config file: {args.config}")
        else:
            print(f"Config file not found: {args.config}")
            exit(1)
    else:
        print("No config file provided. Generating one.")
        generate_config()    
def write_key(ssh_key):
    # Writes public ssh key to user-data file, whether given through argument or input
    if os.path.exists(ssh_key) and ssh_key.endswith(".pub"):
        f = open("user-data", "a")
        f.write("  ssh:\n")
        f.write("    install-server: true\n")
        f.write("    authorized_keys:\n")
        k = open(ssh_key, "r")
        f.write("      - " + k.read())
        
        k.close()
        f.close()
    else:
        return None
def generate_config():
    # Generates basic config file
    import hashlib

    hostname = input("Hostname (ENTER for default - 'ubuntu-server'): ") or "ubuntu-server"
    username = input("Username (ENTER for default - 'ubuntu'): ") or "ubuntu"
    password = hashlib.sha512(input("Password (ENTER for default - 'ubuntu'): ").encode('utf-8')).hexdigest() or "$6$8h9rdUGI5jgt6UuX$RV6oDFTsO8kMcHObuv0JlDI3ET5rRoxh.pEyT6LHAtE/gZtEgG9RQninlaeUlyvN36wz6xLGOhKoVh1AcoL4F."
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    f = open("meta-data", "w")
    f.close()

    f = open("user-data", "w")
    f.write("#cloud-config\n")
    f.write("autoinstall:\n")
    f.write("  version: 1\n")
    f.write("  identity:\n")
    f.write(f"    hostname: {hostname}\n")
    f.write(f"    username: {username}\n")
    f.write(f"    password: {password}\n")
    print("User created successfully.")
    f.close()
    if(args.ssh is not None):
        write_key(args.ssh)
    else:
        ssh_include = input("Do you want to include an ssh key? (Y/N): ")
        if ssh_include == "y" or ssh_include == "Y":
            ssh_key = input("Enter path to your public ssh key (e.g. /home/user/.ssh/id_rsa.pub): ")
            if(write_key(ssh_key) is not None):
                print("SSH public key added successfully.")
            else:
                print("Provided key path does not exist, or script is missing privileges. Skipping...")
        else:
            print("Skipping ssh key configuration.")
    
    print(f"User-data config file generated: {os.getcwd()}/user-data")

def generate_grub():
    # Generates grub bootloader config
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    print("Creating grub.cfg...")

    f = open(GRUB_CONFIG, "w")
    f.write(f"set timeout={args.time}\n")
    f.write("loadfont unicode\n")
    f.write("set menu_color_normal=white/black\n")
    f.write("set menu_color_highlight=black/light-gray\n")

    f.write("menuentry 'Autoinstall' {\n")
    f.write("   set gfxpayload=keep\n")
    f.write("   linux	/casper/vmlinuz autoinstall ds=nocloud\;s=/cdrom/server/  ---\n")
    f.write("   initrd	/casper/initrd\n")
    f.write("}\n")

    f.write("menuentry 'Manual install' {\n")
    f.write("   set gfxpayload=keep\n")
    f.write("   linux	/casper/vmlinuz  ---\n")
    f.write("   initrd	/casper/initrd\n")
    f.write("}\n")

    f.write("grub_platform\n")
    f.write("if [ $grub_platform = \"efi\" ]; then\n")
    f.write("menuentry 'Boot from next volume' {\n")
    f.write("   exit 1\n")
    f.write("}\n")

    f.write("menuentry 'UEFI Firmware Settings' {\n")
    f.write("   fwsetup\n")
    f.write("}\n")

    f.write("menuentry 'Test memory' {\n")
    f.write("   linux16 /boot/memtest86+x64.bin\n")
    f.write("}\n")
    f.write("fi\n")
    f.close()

    print("grub.cfg successfully generated.")

def cleanup():
    # Removes generated files
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    if os.path.exists("user-data") and args.config is None:
        os.remove("user-data")
    if os.path.exists("meta-data"):
        os.remove("meta-data")
    if os.path.exists(GRUB_CONFIG):
        os.remove(GRUB_CONFIG)

def get_input():
    get_output_path()
    get_iso()
    get_config()
    generate_grub()
    edit_iso()
    cleanup()
    
if __name__ == "__main__":
    get_input()