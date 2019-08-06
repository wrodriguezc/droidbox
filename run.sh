#!/bin/bash
pkill adb
pkill emulator64-arm
echo -e "\e[1;32;40mDroidbox Docker starting\nWaiting for the emulator to startup..."
mkdir -p /samples/out
/sbin/ifconfig eth0 | grep 'inet addr:' | cut -d: -f2 | awk '{ print $1}' > /samples/out/ip.txt
sleep 1
/opt/android-sdk-linux/tools/emulator64-arm @droidbox -no-window -no-audio -system /opt/DroidBox_4.1.1/images/system.img -ramdisk /opt/DroidBox_4.1.1/images/ramdisk.img  >> /samples/out/emulator.log &
sleep 1
#service ssh start
adb wait-for-device 
adb forward tcp:5900 tcp:5901
adb shell /data/fastdroid-vnc >> /samples/out/vnc.log &
echo -ne "\e[0m"
python /opt/DroidBox_4.1.1/scripts/droidbox.py $1 $2 2>&1 |tee /samples/out/analysis.log
echo -ne "\e[0m"
exit