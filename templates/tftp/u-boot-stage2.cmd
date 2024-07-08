echo "get the bitfile"
tftpboot {{scratch_addr}} {{core_rbf}}
echo "program the fpga"
dcache flush
fpga load 0 {{scratch_addr}} ${filesize}
bridge enable
echo "get the efi loader and device tree"
tftpboot {{ '0x%0x' % loader_addr }} {{ loader }}
tftpboot {{ '0x%0x' % dtb_addr }} {{ dtb }}
echo "bootefi"
bootefi {{ '0x%0x' % loader_addr }} {{ '0x%0x' % dtb_addr }}
