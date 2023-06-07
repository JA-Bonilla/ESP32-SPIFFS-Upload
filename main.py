import json
import os
import subprocess
import tkinter as tk
import zipfile
from tkinter import filedialog

from serial.tools import list_ports

# Config path for ESP32 devices
CONFIG_PATH = 'device_config.json'

# Load the config to a constant
with open(CONFIG_PATH, 'r') as f:
    CONFIG = json.load(f)

# Baud Rate constant necessary for uploading data to the ESP32
BAUD_RATE = CONFIG['baud_rate']

# Enable or disable console output
DISABLE_CONSOLE_OUTPUT = True

# ESP32 flash memory chunk size
CHUNK_SIZE = 0x1000

# Device status constants
DEVICE_FOUND = 0
DEVICE_FOUND_OUTPUT = 'ESP device found. Ready to upload.'

BOOT_MODE_ERROR = 1
BOOT_MODE_ERROR_TEXT = 'Wrong boot mode detected'
BOOT_MODE_ERROR_OUTPUT = 'ESP device not in proper boot mode. Please put the device in download mode.'

NO_DEVICE_FOUND = 2
NO_DEVICE_FOUND_TEXT = 'fatal error occurred: Failed to connect'
NO_DEVICE_FOUND_OUTPUT = 'No ESP device found. Please attach the device through a USB port.'


current_status = None


def get_used_ports():
    # Gets all used ports
    ports = list(list_ports.comports())
    return [tuple(p) for p in ports]


def get_device():
    # Find port of ESP
    ports = get_used_ports()
    for port in ports:

        # Create ESP32 device instance
        device = ESP32(port[0])
        # Check if device/port is valid
        status = device.check_status()
        if status == DEVICE_FOUND:
            return device, status
        # Check if device is in improper boot mode
        if status == BOOT_MODE_ERROR:
            return None, status

    else:
        # No valid ports, indicate failure by returning None
        return None, NO_DEVICE_FOUND


class ESP32:
    def __init__(self, port):
        self.port = port

    def check_status(self):
        # Run esptool status check
        result = subprocess.run(['esptool', '--port', self.port, '--baud', BAUD_RATE, 'flash_id'], capture_output=True)
        # Get result text from stdout
        text = result.stdout.decode()
        if not DISABLE_CONSOLE_OUTPUT:
            print(text)
        # Check for boot mode error
        if BOOT_MODE_ERROR_TEXT in text:
            return BOOT_MODE_ERROR
        # Check for any other error
        if NO_DEVICE_FOUND_TEXT in text:
            return NO_DEVICE_FOUND
        # Status is good
        return DEVICE_FOUND

    def upload_file(self, address, file_path):
        # Upload the given file path
        result = subprocess.run(['esptool', '--port', self.port, '--baud', str(BAUD_RATE), 'write_flash',
                                 '--flash_size=detect', hex(address), f'{file_path}'], check=True, capture_output=True)
        if not DISABLE_CONSOLE_OUTPUT:
            print(result.stdout.decode())

    def upload_program(self, address, file_path):
        # Upload the given file path
        result = subprocess.run(['esptool', '--port', self.port, '--baud', str(BAUD_RATE), 'write_flash',
                                 '--flash_size=detect', hex(address), f'{file_path}'], check=True, capture_output=True)
        if not DISABLE_CONSOLE_OUTPUT:
            print(result.stdout.decode())

    def clear_flash(self):
        # Clear the flash memory
        result = subprocess.run(['esptool', '--port', self.port, '--baud', str(BAUD_RATE), 'erase_flash'], check=True,
                                capture_output=True)
        if not DISABLE_CONSOLE_OUTPUT:
            print(result.stdout.decode())


class GUI(tk.Tk):
    """GUI class for uploading ZIP files to an ESP32."""

    def __init__(self, ):
        # Initialize tk.Tk class
        super().__init__()

        # Title the GUI
        self.title('ESP32 Uploader')

        # Size the GUI
        self.geometry('600x500')

        # Create a title label
        self.title = tk.Label(self, text='Welcome to ESP32 Uploading Tool!', font=("Arial", 24))
        self.title.pack(padx=5, pady=30)

        # Create a button to upload the ZIP file
        self.button = tk.Button(self, text='Upload ZIP File', command=self.upload_zip_folder, font=("Arial", 16), bg='lightgray')
        self.button.pack(padx=5, pady=30)

        # Create a label to with status
        self.status = tk.Label(self, text=f'Checking for an ESP device...', font=("Arial", 12),
                               wraplength=400, justify=tk.LEFT)
        self.status.pack(padx=5, pady=30)

        # Create a label with instructions
        self.instructions = tk.Label(self, text=f'Instructions: {CONFIG["instructions"]}', font=("Arial", 12), wraplength=400, justify=tk.LEFT)
        self.instructions.pack(padx=5, pady=30)

    def run(self):
        # Run the GUI

        # Create ESP32 check task
        def task():
            global current_status

            # Try to find an ESP32 device
            _, current_status = get_device()

            # Output status text for device found
            if current_status == DEVICE_FOUND:
                self.status.config(text=DEVICE_FOUND_OUTPUT)
                # Reschedule task after 10 seconds
                return

            # Output status text for boot mode error
            if current_status == BOOT_MODE_ERROR:
                self.status.config(text=BOOT_MODE_ERROR_OUTPUT)

            # Output status text for no device found
            if current_status == NO_DEVICE_FOUND:
                self.status.config(text=NO_DEVICE_FOUND_OUTPUT)

            # Reschedule task after 1 second
            self.after(1000, task)

        # Schedule task after 1 second
        self.after(1000, task)

        # Run the tkinter mainloop
        self.mainloop()

    def upload_zip_folder(self):
        # Selects a file from GUI and uploads it to ESP32

        # Make sure device status is good before asking for file
        global current_status
        if current_status is not DEVICE_FOUND:
            # Indicate failure by return false
            return False

        # Open a file dialog and get the selected folder
        file_path = filedialog.askopenfilename(title="Select a ZIP File", filetypes=(('zip files', '*.zip'),))

        self.status.config(text='Uploading files... (this may take a while)')
        self.update()

        device, _ = get_device()
        if device is None:
            # If no device indicate failure by returning False
            self.after(1000, task)
            return False

        # Clear flash memory in the ESP32
        device.clear_flash()

        # Read in zip file
        with zipfile.ZipFile(file_path) as zip:

            # Set current address
            current_address = 0x0

            file_list = [file_name for file_name in zip.filelist if file_name.filename.endswith('.bin')]
            file_list.extend(file_name for file_name in zip.filelist if not file_name.filename.endswith('.bin'))

            # Iterate through files in zip
            print(f'Uploading ZIP file contents... ({len(file_list)} files)')
            for i, file_name in enumerate(file_list, 1):
                # Skip unwanted files
                if file_name.filename in [None, '/']:
                    continue

                # Read contents of file
                f = zip.open(file_name, mode='r')

                # Open temp file
                file_name = file_name.filename
                print(f'  ({i}) - {file_name}')
                temp_path = f'temp{file_name[file_name.rindex("."):]}'
                with open(temp_path, 'wb') as temp:
                    temp.write(bytes(f.read()))

                # Close file
                f.close()

                # Upload the file to the ESP32
                if file_name.endswith('.bin'):
                    device.upload_program(current_address, temp_path)
                else:
                    device.upload_file(current_address, temp_path)

                # Get file size and calculate new address
                size = os.path.getsize(temp_path)
                current_address = ((current_address + size) // CHUNK_SIZE + 1) * CHUNK_SIZE

                # Remove temp file
                os.remove(temp_path)

        print('File uploading complete!')
        self.status.config(text='Files uploaded successfully!')

        # Indicate success by returning True
        return True


def main():
    gui = GUI()
    gui.run()


if __name__ == '__main__':
    main()
