#!/bin/sh

#Remove all previous data
rm -rf /data/dynamic_analysis/$1

#Create required directories
mkdir -p /data/dynamic_analysis && mkdir /data/dynamic_analysis/$1 && mkdir /data/dynamic_analysis/$1/logs && mkdir /data/dynamic_analysis/$1/out

#Create symbolic link required by Droidbox output
rm /samples 2> /dev/null
ln -s /data/dynamic_analysis/$1 /samples

#Kill adb if already running
pkill adb
#Kill the emulator if already running
pkill emulator64-arm

echo -e "\e[1;32;40mDroidbox Docker starting\nWaiting for the emulator to startup..."

#Launch emulator
sleep 1
/opt/android-sdk-linux/tools/emulator64-arm @droidbox -no-window -no-audio -system /opt/DroidBox_4.1.1/images/system.img -ramdisk /opt/DroidBox_4.1.1/images/ramdisk.img  >> /data/dynamic_analysis/$1/logs/emulator.log &
sleep 1

#Start emulator services
adb wait-for-device 
adb forward tcp:5900 tcp:5901
adb shell /data/fastdroid-vnc >> /data/dynamic_analysis/$1/logs/vnc.log &

echo -ne "\e[0m"
python /opt/DroidBox_4.1.1/scripts/droidbox.py /data/samples/$1/$2 $3 2>&1 |tee /data/dynamic_analysis/$1/logs/analysis.log
echo -ne "\e[0m"
exit
