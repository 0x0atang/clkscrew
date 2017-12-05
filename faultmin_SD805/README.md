### Setup
Prepare the device to the assumed state using the following commands:
```
stop thermal-engine
stop mpdecision
echo 1 > /sys/devices/system/cpu/cpu1/online
echo 1 > /sys/devices/system/cpu/cpu2/online
echo 0 > /sys/devices/system/cpu/cpu3/online
echo userspace > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
echo userspace > /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor
echo userspace > /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor
echo 2649600 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed
echo 2649600 > /sys/devices/system/cpu/cpu1/cpufreq/scaling_setspeed
echo 2649600 > /sys/devices/system/cpu/cpu2/cpufreq/scaling_setspeed
```

Try to get the temperature of the device to above 33 degree celsius.
```
cat /sys/devices/virtual/thermal/thermal_zone0/temp
```

### Run
Command to run with the glitching parameters:
```
adb shell su -c "insmod /data/local/tmp/glitchmin.ko" PARAM_gval=0xd0 PARAM_volt=1055000 PARAM_gdelay=5 PARAM_delaypre=8000
```

Expected output of normal operation:
```
<6>[  857.974989] glitchmin: |---- ,ITER-01,0xd0,5,8000,0,1055000
<6>[  857.976840] glitchmin: | ,slave,PASS
```

Expected output of a glitched operation:
```
<6>[  858.985222] glitchmin: |---- ,ITER-02,0xd0,5,8000,0,1055000
<6>[  858.987077] glitchmin: | ,slave,FAIL
<6>[  858.987151] glitchmin: | ,slave,EXPT_TEST,0,c44dc735f6682a261a0b8545a62dd13df4c646a5ede482cef858925baa1811fa0284766b3d1d2b4d6893df4d9c045efe3e84d8c5d03631b25420f1231d8211e2
<6>[  858.987223] glitchmin: | ,slave,EXPT_TEST,1,322eb7eb524da6c1e8fb4c3ae4a8f5ca13d1e0591f5c64e8e711b3726215cec59ed0ebc6bb042b917d44528887915fdf764df691d183e16f31ba1ed94c84b476
<6>[  858.987294] glitchmin: | ,slave,EXPT_TEST,2,e74b488463e85551022021763af35a64ddf105c1530ef3fcf7e54233e5d3a4747bbb17328a63e6e3384ac25ee80054bd566855e2eb59a2fd168d3643e44851ac
<6>[  858.987369] glitchmin: | ,slave,EXPT_TEST,3,f0d118fb03bcbcbc099b4add59c39367d6c91f498d8d607af2e57cc73e3b5718435a81123f080267726a2a9c1cc94b9c6bb6817427b85d8c670f9a53a777511b
```

### Demo
[asciinema link](https://asciinema.org/a/5vvn3s9nzula930xui1z7tg65)