#!/usr/bin/python3

import requests
import sys
import time
import board
import neopixel
import subprocess

num_pixels = 36
pixels = neopixel.NeoPixel(board.D18, num_pixels, brightness=0.2)

lastStatus = None
lastConnectStatus = True

#pixels[0] = (255, 0, 0)

__original_author__ = 'Andres Torti'
__edited_by__ = 'Brian Jackson'

octohost = '127.0.0.1'
octoport = '5000'
octoapikey = '7DF42B1B487843048538B7E0851563F3'

def colorFadeTwo(colorFrom, colorTo, wait_ms=5, steps=50):
	#ssteps = 200
	step_R = (colorTo[0] - colorFrom[0]) / steps
	step_G = (colorTo[1] - colorFrom[1]) / steps
	step_B = (colorTo[2] - colorFrom[2]) / steps  
	r = int(colorFrom[0])
	g = int(colorFrom[1])
	b = int(colorFrom[2])

	for x in range(steps):
		#print(int(r), int(g), int(b))
		fillTwo(int(r), int(g), int(b))
		time.sleep(wait_ms / 1000.0)
		r += step_R
		g += step_G
		b += step_B

def switchLights(status):
	if status == 0:
		subprocess.run(["gpio", "-g", "mode", "17", "in"])
	elif status == 1:
		subprocess.run(["gpio", "-g", "mode", "17", "out"])

def fillTwo(r, g, b):
	pixels.fill((0, 0, 0))
	halfPixel1 = round(num_pixels/2)
	halfPixel2 = round((num_pixels/2)-1)
	pixels[halfPixel1] = (r, g, b)
	pixels[halfPixel2] = (r, g, b)
	
def wheel(pos):
    # Input a value 0 to 255 to get a color value.
    # The colours are a transition r - g - b - back to r.
    if pos < 0 or pos > 255:
        r = g = b = 0
    elif pos < 85:
        r = int(pos * 3)
        g = int(255 - pos*3)
        b = 0
    elif pos < 170:
        pos -= 85
        r = int(255 - pos*3)
        g = 0
        b = int(pos*3)
    else:
        pos -= 170
        r = 0
        g = int(pos*3)
        b = int(255 - pos*3)
    return (r, g, b)

def rainbow_cycle(wait):
    for j in range(255):
        for i in range(num_pixels):
            pixel_index = (i * 256 // num_pixels) + j
            pixels[i] = wheel(pixel_index & 255)
        pixels.show()
        time.sleep(wait)

class OctoprintAPI:
    """
    This class is an interface for the Octoprint server API
	
	Brian: keeping these as is, in case of future expansion.
    """

    def __init__(self, address, port, api_key):
        self.host = address
        self.s = requests.Session()
        self.s.headers.update({'X-Api-Key': api_key,
                               'Content-Type': 'application/json'})

        # Base address for all the requests
        self.base_address = 'http://' + address + ':' + str(port)

    def connect_to_printer(self, port=None, baudrate=None, printer_profile=None, save=None, autoconnect=None):
        """
        Connects to the printer
        :param port: [Optional] port where the printer is connected (ie: COMx in Windows, /dev/ttyXX in Unix systems).
                if not specified the current selected port will be used or if no port is selected auto detection will
                be used
        :param baudrate: [Optional] baud-rate, if not specified the current baud-rate will be used ot if no baud-rate
                is selected auto detection will be used
        :param printer_profile: [Optional] printer profile to be used for the connection, if not specified the default
                one will be used
        :param save: [Optional] whether to save or not the connection settings
        :param autoconnect: [Optional] whether to connect automatically or not on the next Ocotprint start
        """
        data = {'command': 'connect'}
        if port is not None:
            data['port'] = port
        if baudrate is not None:
            data['baudrate'] = baudrate
        if printer_profile is not None:
            data['printerProfile'] = printer_profile
        if save is not None:
            data['save'] = save
        if autoconnect is not None:
            data['autoconnect'] = autoconnect

        r = self.s.post(self.base_address + '/api/connection', json=data)
        if r.status_code != 204:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

    def is_printer_connected(self):
        """
        Checks if the printer is connected to the Octoprint server
        :return: True if connected, False if not
        """
        if self.s.get(self.base_address + '/api/printer').status_code != 200:
            return False
        else:
            return True

    def get_printer_status(self):
        """
        Get the printer status
        :return: string with the printer status (Operational, Disconnected, ...). Returns an empty string
                    if there was an error trying to get the status.
        :raise: TypeError when failed to get printer status
        """
        r = self.s.get(self.base_address + '/api/printer')
        data = r.content.decode('utf-8').split('\n')
        for line in data:
            if 'text' in line:
                # check if null
                if 'null' in line:
                    raise Exception('Error trying to get printer status')
                else:
                    return line[line.find(':')+3:line.find(',')]

        # Default response from Octoprint
        return data[0]

    def set_bed_temp(self, temp):
        """
        Set the bed temperature
        :param temp: desired bed temperature
        """
        r = self.s.post(self.base_address + '/api/printer/bed', json={'command': 'target', 'target': temp})
        if r.status_code != 204:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

    def get_bed_temp(self):
        """
        Get the current bed temperature
        :return: current bed temperature. Returns -1 y there was some error getting the temperature.
        """
        r = self.s.get(self.base_address + '/api/printer/bed')
        if r.status_code != 200:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

        data = r.content.decode('utf-8').split('\n')
        for line in data:
            if 'target' in line:
                return int(float(line[line.find(':')+1:]))

        raise Exception("Error getting bed temperature - " + r.content)

    def pause_job(self):
        """
        Pause the current job
        """
        r = self.s.post(self.base_address + '/api/job', json={'command': 'pause'})
        if r.status_code != 204:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

    def resume_job(self):
        """
        Resume the current job
        """
        r = self.s.post(self.base_address + '/api/job', json={'command': 'pause'})
        if r.status_code != 204:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

    def start_job(self):
        """
        Start printing with the currently selected file
        """
        r = self.s.post(self.base_address + '/api/job', json={'command': 'start'})
        if r.status_code != 204:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

    def cancel_job(self):
        """
        Cancel the current job
        """
        r = self.s.post(self.base_address + '/api/job', json={'command': 'cancel'})
        if r.status_code != 204:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

    def get_version(self):
        """
        Get Octoprint version
        :return: string with Octoprint version. It returns '0.0.0' if there was an error obtaining the version
        """
        r = self.s.get(self.base_address + '/api/version')
        if r.status_code != 200:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

        data = r.content.decode('utf-8').split('\n')
        for line in data:
            if 'server' in line:
                return line[line.find(':')+3:-1]

        return '0.0.0'

    def get_print_progress(self):
        """
        Get the print progress as a percentage
        :return: float indicating the current print progress
        """
        r = self.s.get(self.base_address + '/api/job')
        if r.status_code != 200:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

        data = r.content.decode('utf-8').split('\n')
        for line in data:
            if 'completion' in line:
                # check if null
                if 'null' in line:
                    raise Exception('Error reading print progress')
                else:
                    return int(float(line[line.find(':')+1:line.find(',')]))
        return 0

    def get_total_print_time(self):
        """
        Get the total print time in seconds
        :return: total print time in seconds
        """
        r = self.s.get(self.base_address + '/api/job')
        if r.status_code != 200:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

        data = r.content.decode('utf-8').split('\n')
        for line in data:
            if 'estimatedPrintTime' in line:
                # check if null
                if 'null' in line:
                    raise Exception('Error reading total print time')
                else:
                    return int(float(line[line.find(':')+1:line.find(',')]))
        return 0

    def get_print_time_left(self):
        """
        Get the print time left of the current job in seconds
        :return: print time left in seconds
        """
        r = self.s.get(self.base_address + '/api/job')
        if r.status_code != 200:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

        data = r.content.decode('utf-8').split('\n')
        for line in data:
            if 'printTimeLeft' in line:
                # check if null
                if 'null' in line:
                    raise Exception('Error reading print time left')
                else:
                    return int(float(line[line.find(':')+1:]))
        return 0

    def get_elapsed_print_time(self):
        """
        Get the elapsed print time in seconds of the current job
        :return: elapsed print time in seconds
        """
        r = self.s.get(self.base_address + '/api/job')
        if r.status_code != 200:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

        data = r.content.decode('utf-8').split('\n')
        for line in data:
            if 'printTime' in line:
                # check if null
                if 'null' in line:
                    raise Exception('Error reading elapsed print time')
                else:
                    return int(float(line[line.find(':')+1:line.find(',')]))
        return 0

    def get_file_printing(self):
        """
        Get the name of the current file being printed
        :return: name of the file being printed
        """
        r = self.s.get(self.base_address + '/api/job')
        if r.status_code != 200:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

        data = r.content.decode('utf-8').split('\n')
        for line in data:
            if 'name' in line:
                # check if null
                if 'null' in line:
                    raise Exception('Error reading filename being printed')
                else:
                    return line[line.find(':')+1:line.find(',')].replace('"', '').strip()
        return ''

    def send_gcode(self, gcode):
        """
        Sends one or multiple comma separated G-codes to the printer
        :param gcode: G-Code/s to send as a list containing all the G-codes to send
        """
        r = self.s.post(self.base_address + '/api/printer/command', json={'commands': gcode})
        if r.status_code != 204:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

    def select_file(self, file_name):
        r = self.s.post(self.base_address + '/api/files/local/' + file_name, json={'command': 'select', 'print': True})
        if r.status_code != 200:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

    def get_extruder_target_temp(self):
        """
        Get the target extruder temperature in degrees celsius
        :return: target extruder temperature in degrees celsius
        """
        r = self.s.get(self.base_address + '/api/printer/tool')
        if r.status_code != 200:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

        data = r.content.decode('utf-8').split('\n')
        for line in data:
            if 'target' in line:
                if 'null' in line:
                    raise Exception('Error retrieving extruder temperature')
                else:
                    return int( round(float(line[line.find(':')+1:line.find(',')]), 0) )
        return 0

    def get_extruder_current_temp(self):
        """
        Get the current extruder temperature in degrees celsius
        :return: current extruder temperature in degrees celsius
        """
        r = self.s.get(self.base_address + '/api/printer/tool')
        if r.status_code != 200:
            raise Exception("Error: {code} - {content}".format(code=r.status_code, content=r.content.decode('utf-8')))

        data = r.content.decode('utf-8').split('\n')
        for line in data:
            if 'actual' in line:
                return int( round(float(line[line.find(':')+1:line.find(',')]), 0) )
        return 0


def run_and_handle(method):
    """
    Just a clean way to call any function and print the returned value to 'stdout' if valid or print the error message to
        to 'stderr'
    :param method: function to execute
    :param _args: arguments to pass to the function
    :return: None
    """
    try:
        result = method()
        if result is not None:
            return(result)
    except Exception as e:
        print(str(e), file=sys.stderr)

while True:
	if __name__ == '__main__':

		# Create the Octoprint interface
		octo_api = OctoprintAPI(octohost, octoport, octoapikey)

		isPrinterConnected = run_and_handle(octo_api.is_printer_connected)

		# Printer options
		if isPrinterConnected == True:
		
			lastConnectStatus = 'Connected'
			print ("Printer Connection:  Established")
			
			printerStatus = run_and_handle(octo_api.get_printer_status)
			
			#first we'll want too check if the status is different from the last go round
			#we want to skip the LED change if it is, because redrawing sucks!
			
			if printerStatus != lastStatus:
			
				if printerStatus == 'Operational' and printerStatus != 'Printing':
					print ("Printer Status:  Operational")
					colorFadeTwo([0, 0, 255], [0, 255, 0])
					switchLights(1)
					lastStatus = 'Operational'	
						
				elif printerStatus == 'Disconnected':
					print ("Printer is not connected")
					colorFadeTwo([0, 255, 0], [0, 0, 255])
					switchLights(0)
					lastConnectStatus = False
					lastStatus = 'Disconnected'
				else:
					print ("Could not determine printer status")
				
			#unless it's Printing, because we want to do progress bar updates
			if printerStatus == 'Printing':
				print ("Printer Status:  Printing")
				
				printerProgress = run_and_handle(octo_api.get_print_progress)
				
				if printerProgress is not None:
					printerProgress = printerProgress/100
					
					print ("Printer Status:")
					print (printerProgress)
					
					numLights = round(num_pixels * printerProgress)
					print ("Number of LEDS")
					print (numLights)

					for y in range((num_pixels-1)-numLights, 0, -1):
						pixels[y] = (255, 0, 0)				
					for x in range(num_pixels-1, num_pixels-numLights, -1):
						pixels[x] = (0, 255, 0)
						
				elif printerProgress is None:
					print ("Could not get progress of printer")
				
				lastStatus = 'Printing'	
			
			lastConnectStatus = True
			
			#print ("Printer status output: ")
			#print (printerStatus)
		
		#not connected, so let's make it blue and turn off the lights
		else:
			if lastConnectStatus == True and isPrinterConnected == False:
				print ("Printer is not connected")
				colorFadeTwo([0, 255, 0], [0, 0, 255])
				switchLights(0)
				lastConnectStatus = False
				lastStatus = 'Disconnected'
		
		'''
		Also keeping these for future expansion
		'''
		#print (run_and_handle(octo_api.is_printer_connected))

		# elif args.connect:
			# run_and_handle(octo_api.connect_to_printer, args.printer_port, args.baudrate, args.profile, args.save,
						   # args.autoconnect)

		# elif args.printer_status:
			# run_and_handle(octo_api.get_printer_status)

		# elif args.print_progress:
			# run_and_handle(octo_api.get_print_progress)

		# elif args.total_time:
			# run_and_handle(octo_api.get_total_print_time)

		# elif args.left_time:
			# run_and_handle(octo_api.get_print_time_left)

		# elif args.elapsed_time:
			# run_and_handle(octo_api.get_elapsed_print_time)

		# elif args.printing_file:
			# run_and_handle(octo_api.get_file_printing)

		# elif args.send_gcode:
			# run_and_handle(octo_api.send_gcode, args.send_gcode)

		# elif args.select_file:
			# run_and_handle(octo_api.select_file, args.select_file[0])

		# # Extruder
		# elif args.ext_temp:
			# run_and_handle(octo_api.get_extruder_current_temp)

		# elif args.ext_target:
			# run_and_handle(octo_api.get_extruder_target_temp)

		# # Bed options
		# elif args.set_bed_temp:
			# if args.set_bed_temp < 0:
				# print('Error, bed temperature can\'t be negative', file=sys.stderr)
			# else:
				# run_and_handle(octo_api.set_bed_temp, args.set_bed_temp)

		# elif args.get_bed_temp:
			# run_and_handle(octo_api.get_bed_temp)

		# # Job options
		# elif args.pause:
			# run_and_handle(octo_api.pause_job)

		# elif args.resume:
			# run_and_handle(octo_api.resume_job)

		# elif args.start:
			# run_and_handle(octo_api.start_job)

		# elif args.cancel:
			# run_and_handle(octo_api.cancel_job)

		# # Other options
		# elif args.octo_version:
			# run_and_handle(octo_api.get_version)

		# elif args.version:
			# print('1.0.0')

	time.sleep(5)
