set architecture aarch64
target extended-remote localhost:3333
set remotetimeout 4000
restore /home/de10-user/de10playground-payload/tftp/u-boot-dtb.bin binary 0x1000
restore /opt/uboot-init-bootp.scr binary 0x2100000
set $pc = 0x1000
continue
