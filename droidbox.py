################################################################################
# (c) 2011, The Honeynet Project
# Author: Patrik Lantz patrik@pjlantz.com and Laurent Delosieres ldelosieres@hispasec.com
#
# This program is free software you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#
################################################################################

"""Analyze dynamically Android applications

This script allows you to analyze dynamically Android applications. It installs, runs, and analyzes Android applications.
At the end of each analysis, it outputs the Android application's characteristics in JSON.
Please keep in mind that all data received/sent, read/written are shown in hexadecimal since the handled data can contain binary data.
"""

import sys, json, time, curses, signal, os, inspect
import zipfile, StringIO
import tempfile, shutil
import operator
import subprocess
import thread, threading
import re
import os

from threading import Thread
from xml.dom import minidom
from subprocess import call, PIPE, Popen
from utils import AXMLPrinter
import hashlib
from pylab import *
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.font_manager import FontProperties

from collections import OrderedDict

sendsms = {}
phonecalls = {}
cryptousage = {}
dexclass = {}
dataleaks = {}
opennet = {}
sendnet = {}
recvnet = {}
closenet = {}
fdaccess = {}
servicestart = {}
accessedfiles = {}

tags = { 0x1 :   "TAINT_LOCATION",      0x2: "TAINT_CONTACTS",        0x4: "TAINT_MIC",            0x8: "TAINT_PHONE_NUMBER",
         0x10:   "TAINT_LOCATION_GPS",  0x20: "TAINT_LOCATION_NET",   0x40: "TAINT_LOCATION_LAST", 0x80: "TAINT_CAMERA",
         0x100:  "TAINT_ACCELEROMETER", 0x200: "TAINT_SMS",           0x400: "TAINT_IMEI",         0x800: "TAINT_IMSI",
         0x1000: "TAINT_ICCID",         0x2000: "TAINT_DEVICE_SN",    0x4000: "TAINT_ACCOUNT",     0x8000: "TAINT_BROWSER",
         0x10000: "TAINT_OTHERDB",      0x20000: "TAINT_FILECONTENT", 0x40000: "TAINT_PACKAGE",    0x80000: "TAINT_CALL_LOG",
         0x100000: "TAINT_EMAIL",       0x200000: "TAINT_CALENDAR",   0x400000: "TAINT_SETTINGS" }

class CountingThread(Thread):
    """
    Used for user interface, showing in progress sign 
    and number of collected logs from the sandbox system
    """

    def __init__ (self):
        """
        Constructor
        """
        
        Thread.__init__(self)
        self.stop = False
        self.logs = 0
        
    def stopCounting(self):
        """
        Mark to stop this thread 
        """
        
        self.stop = True
        
    def increaseCount(self):
        
        self.logs = self.logs + 1

    def run(self):
        """
        Update the progress sign and 
        number of collected logs
        """
        
        signs = ['|', '/', '-', '\\']
        counter = 0
        while 1:
            sign = signs[counter % len(signs)]
            sys.stdout.write("     \033[132m[%s] Collected %s sandbox logs\033[1m   (Ctrl-C to view logs)\r" % (sign, str(self.logs)))
	    sys.stdout.flush()
            time.sleep(0.5)
            counter = counter + 1
            if self.stop:
                sys.stdout.write("   \033[132m[%s] Collected %s sandbox logs\033[1m%s\r" % ('*', str(self.logs), ' '*25))
		sys.stdout.flush()
                break
               
class Application:
     """
     Used for extracting information of an Android APK
     """
     def __init__(self, filename):
	self.filename = filename
	self.packageNames = []
	self.enfperm = []
	self.permissions = []
	self.recvs = []
	self.activities = {}
	self.recvsaction = {}

	self.mainActivity = None

     def processAPK(self):
	 xml = {}
	 error = True
	 try:
		 zip = zipfile.ZipFile(self.filename)

		 for i in zip.namelist() :
			if i == "AndroidManifest.xml" :
				try :
					xml[i] = minidom.parseString( zip.read( i ) )
				except :
					xml[i] = minidom.parseString( AXMLPrinter( zip.read( i ) ).getBuff() )

				for item in xml[i].getElementsByTagName('manifest'):
					self.packageNames.append( str( item.getAttribute("package") ) )

				for item in xml[i].getElementsByTagName('permission'):
					self.enfperm.append( str( item.getAttribute("android:name") ) )

				for item in xml[i].getElementsByTagName('uses-permission'):
					self.permissions.append( str( item.getAttribute("android:name") ) )

				for item in xml[i].getElementsByTagName('receiver'):
					self.recvs.append( str( item.getAttribute("android:name") ) )
					for child in item.getElementsByTagName('action'):
						self.recvsaction[str( item.getAttribute("android:name") )] = (str( child.getAttribute("android:name") ))

				for item in xml[i].getElementsByTagName('activity'):
					activity = str( item.getAttribute("android:name") )
					self.activities[activity] = {}
					self.activities[activity]["actions"] = list()
			
					for child in item.getElementsByTagName('action'):
						self.activities[activity]["actions"].append(str(child.getAttribute("android:name")))

				for activity in self.activities:
					for action in self.activities[activity]["actions"]:
						if action == 'android.intent.action.MAIN':
							self.mainActivity = activity
				error = False

				break

		 if (error == False):
			return 1
		 else:
			return 0

	 except:
		 return 0

     def getEnfperm(self):
	return self.enfperm
	
     def getRecvsaction(self):
	return self.recvsaction

     def getMainActivity(self):
	return self.mainActivity

     def getActivities(self):
	return self.activities

     def getRecvActions(self):
	return self.recvsaction

     def getPackage(self):
	#One application has only one package name
	return self.packageNames[0]
 
     def getHashes(self, block_size=2**8):
	"""
	Calculate MD5,SHA-1, SHA-256
	hashes of APK input file
	"""

	md5 = hashlib.md5()
	sha1 = hashlib.sha1()
	sha256 = hashlib.sha256()
	f = open(self.filename, 'rb')
	while True:
		data = f.read(block_size)
		if not data:
		    break

		md5.update(data)
		sha1.update(data)
		sha256.update(data)
	return [md5.hexdigest(), sha1.hexdigest(), sha256.hexdigest()]
 
def decode(s, encodings=('ascii', 'utf8', 'latin1')):
    for encoding in encodings:
	try:
	    return s.decode(encoding)
	except UnicodeDecodeError:
	    pass
    return s.decode('ascii', 'ignore')

def getTags(tagParam):
    """
    Retrieve the tag names
    """

    tagsFound = []
    for tag in tags.keys():
        if tagParam & tag != 0:
            tagsFound.append(tags[tag])
    return tagsFound

def hexToStr(hexStr):
    """
    Convert a string hex byte values into a byte string
    """

    bytes = []
    hexStr = ''.join(hexStr.split(" "))
    for i in range(0, len(hexStr), 2):
	bytes.append(chr(int(hexStr[i:i+2], 16)))
    return unicode(''.join( bytes ), errors='replace')


def interruptHandler(signum, frame):
    """ 
	Raise interrupt for the blocking call 'logcatInput = sys.stdin.readline()'
	
	"""
    raise KeyboardInterrupt	

def main(argv):

	if len(argv) < 2 or len(argv) > 3:
		print("Usage: droidbox.py filename.apk output <duration in seconds>")
	        sys.exit(1)
		    
	duration = 0

	#Duration given?
	if len(argv) == 3:
		duration = int(argv[2])

	apkName = sys.argv[1]

	#APK existing?
	if os.path.isfile(apkName) == False:
	    	print("File %s not found" % argv[1])
		sys.exit(1)

	application = Application(apkName)
	ret = application.processAPK()

	#Error during the APK processing?
	if (ret == 0):
		print("Failed to analyze the APK. Terminate the analysis.")
		sys.exit(1)

	activities = application.getActivities()
	mainActivity = application.getMainActivity()
	packageName = application.getPackage()

	recvsaction = application.getRecvsaction()
	enfperm = application.getEnfperm()

	#Get the hashes
	hashes = application.getHashes()

	curses.setupterm()
	sys.stdout.write(curses.tigetstr("clear"))
	sys.stdout.flush()
	call(['adb', 'logcat', '-c'])

	print " ____                        __  ____"
	print "/\  _`\               __    /\ \/\  _`\\"
	print "\ \ \/\ \  _ __  ___ /\_\   \_\ \ \ \L\ \   ___   __  _"  
	print " \ \ \ \ \/\`'__\ __`\/\ \  /'_` \ \  _ <' / __`\/\ \/'\\" 
	print "  \ \ \_\ \ \ \/\ \L\ \ \ \/\ \L\ \ \ \L\ \\ \L\ \/>  </"
	print "   \ \____/\ \_\ \____/\ \_\ \___,_\ \____/ \____//\_/\_\\"
	print "    \/___/  \/_/\/___/  \/_/\/__,_ /\/___/ \/___/ \//\/_/"

	#No Main acitvity found? Return an error
	if mainActivity == None:
		print("No activity to start. Terminate the analysis.")
		sys.exit(1)

	#No packages identified? Return an error
	if packageName == None:
		print("No package found. Terminate the analysis.")
		sys.exit(1)

	#Execute the application
	ret = call(['monkeyrunner', 'monkeyrunner.py', apkName, packageName, mainActivity], stderr=PIPE, cwd=os.path.dirname(os.path.realpath(__file__)))

	if (ret == 1):
		print("Failed to execute the application.")
		sys.exit(1)

	print("Starting the activity %s..." % mainActivity)

	#By default the application has not started
	applicationStarted = 0
	stringApplicationStarted = "Start proc %s" % packageName

	#Open the adb logcat
	adb = Popen(["adb", "logcat", "DroidBox:W", "dalvikvm:W", "ActivityManager:I"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

	#Wait for the application to start
	while 1:
		try:
			logcatInput = adb.stdout.readline()
			if not logcatInput:
                    		raise Exception("We have lost the connection with ADB.")

			#Application started?
			if (stringApplicationStarted in logcatInput):
				applicationStarted = 1
				break;
		except:
			break

	if (applicationStarted == 0):
                print("Analysis has not been done.")
		#Kill ADB, otherwise it will never terminate
	        os.kill(adb.pid, signal.SIGTERM)
                sys.exit(1)

	print("Application started")
	print("Analyzing the application during %s seconds..." % (duration if (duration !=0) else "infinite time"))

	count = CountingThread()
	count.start()

	timeStamp = time.time()
	if duration:
	    signal.signal(signal.SIGALRM, interruptHandler)
	    signal.alarm(duration)

	#Collect DroidBox logs
        lastScreenshot = 0
	while 1:
            if (time.time() - lastScreenshot) >=3:
                #Take Screenshots every 3 seconds.
                os.system("adb shell screencap -p | sed 's/\r$//' > /samples/out/screen_$(date +%Y-%m-%d_%H%M%S).png")
                lastScreenshot = time.time()
	    try:
		logcatInput = adb.stdout.readline() 
		if not logcatInput:
		    raise Exception("We have lost the connection with ADB.")
		
		boxlog = logcatInput.split('DroidBox:')
		if len(boxlog) > 1:
		    try:
			load = json.loads(decode(boxlog[1]))

			# DexClassLoader
			if load.has_key('DexClassLoader'):
			    load['DexClassLoader']['type'] = 'dexload'
			    dexclass[time.time() - timeStamp] = load['DexClassLoader']
			    count.increaseCount()

			# service started
			if load.has_key('ServiceStart'):
			    load['ServiceStart']['type'] = 'service'
			    servicestart[time.time() - timeStamp] = load['ServiceStart']
			    count.increaseCount()

			# received data from net
			if load.has_key('RecvNet'):   
			    host = load['RecvNet']['srchost']
			    port = load['RecvNet']['srcport']

			    recvnet[time.time() - timeStamp] = recvdata = {'type': 'net read', 'host': host, 'port': port, 'data': load['RecvNet']['data']}
			    count.increaseCount()

			# fdaccess
			if load.has_key('FdAccess'):
			    accessedfiles[load['FdAccess']['id']] = hexToStr(load['FdAccess']['path'])

			# file read or write     
			if load.has_key('FileRW'):
			    load['FileRW']['path'] = accessedfiles[load['FileRW']['id']]
			    if load['FileRW']['operation'] == 'write':
			        load['FileRW']['type'] = 'file write'
			    else:
			        load['FileRW']['type'] = 'file read'

			    fdaccess[time.time()-timeStamp] = load['FileRW']
			    count.increaseCount()

			# opened network connection log
			if load.has_key('OpenNet'):
			    opennet[time.time()-timeStamp] = load['OpenNet']
			    count.increaseCount()

			# closed socket
			if load.has_key('CloseNet'):
			    closenet[time.time()-timeStamp] = load['CloseNet']
			    count.increaseCount()

			# outgoing network activity log
			if load.has_key('SendNet'):
			    load['SendNet']['type'] = 'net write'
			    sendnet[time.time()-timeStamp] = load['SendNet']
			    
			    count.increaseCount()                                          

			# data leak log
			if load.has_key('DataLeak'):
			    my_time = time.time()-timeStamp
			    load['DataLeak']['type'] = 'leak'
			    load['DataLeak']['tag'] = getTags(int(load['DataLeak']['tag'], 16))
			    dataleaks[my_time] = load['DataLeak']
			    count.increaseCount()

			    if load['DataLeak']['sink'] == 'Network':
				load['DataLeak']['type'] = 'net write'
				sendnet[my_time] = load['DataLeak']
				count.increaseCount()

			    elif load['DataLeak']['sink'] == 'File':	
				load['DataLeak']['path'] = accessedfiles[load['DataLeak']['id']]
				if load['DataLeak']['operation'] == 'write':
				    load['DataLeak']['type'] = 'file write'
				else:
				    load['DataLeak']['type'] = 'file read'

				fdaccess[my_time] = load['DataLeak']
				count.increaseCount()

			    elif load['DataLeak']['sink'] == 'SMS':
				load['DataLeak']['type'] = 'sms'
				sendsms[my_time] = load['DataLeak']
				count.increaseCount()

			# sent sms log
			if load.has_key('SendSMS'):
			    load['SendSMS']['type'] = 'sms'
			    sendsms[time.time()-timeStamp] = load['SendSMS']
			    count.increaseCount()

			# phone call log
			if load.has_key('PhoneCall'):
			    load['PhoneCall']['type'] = 'call'
			    phonecalls[time.time()-timeStamp] = load['PhoneCall']
			    count.increaseCount()

			# crypto api usage log
			if load.has_key('CryptoUsage'):
			    load['CryptoUsage']['type'] = 'crypto'                                                                   
			    cryptousage[time.time()-timeStamp] = load['CryptoUsage']
			    count.increaseCount()
		    except ValueError:
			pass

	    except:
		try:
			count.stopCounting()
			count.join()
		finally:
			break;
	    
	#Kill ADB, otherwise it will never terminate
	os.kill(adb.pid, signal.SIGTERM)

	#Done? Store the objects in a dictionary, transform it in a JSON object and return it
	output = dict()

	#Sort the items by their key
	output["dexclass"] = dexclass
	output["servicestart"] = servicestart

	output["recvnet"] = recvnet
	output["opennet"] = opennet
	output["sendnet"] = sendnet
	output["closenet"] = closenet

	output["accessedfiles"] = accessedfiles
	output["dataleaks"] = dataleaks

	output["fdaccess"] = fdaccess
	output["sendsms"] = sendsms
	output["phonecalls"] = phonecalls
	output["cryptousage"] = cryptousage

	output["recvsaction"] = recvsaction
	output["enfperm"] = enfperm

	output["hashes"] = hashes
	output["apkName"] = apkName
 
	with open("/tmp/analysis.json", "w", 0) as jsonfile:
		jsonfile.write(json.dumps(output,sort_keys=True, indent=4))
		jsonfile.flush()
		os.fsync(jsonfile.fileno())
		jsonfile.close()

	print(json.dumps(output))

	sys.stdout.flush()
	sys.exit(0)

if __name__ == "__main__":
    main(sys.argv)
