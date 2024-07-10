#! /usr/bin/env sh

PAYLOADDIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

echo "HPS boot payload"

# setup tftpd configuration
################################################################################
cat << EOF > /tmp/tftpd-hpa
TFTP_USERNAME="{{ tftp_user }}"
TFTP_DIRECTORY="${PAYLOADDIR}/tftp"
TFTP_ADDRESS="{{ tftp_addr }}"
TFTP_OPTIONS="{{ ' '.join(tftp_opts) }}"
EOF
echo "generated /tmp/tftpd-hpa"
mount --bind -o ro /tmp/tftpd-hpa /etc/default/tftpd-hpa
echo "bound mounted ${PAYLOADDIR}/conf/tftpd-hpa over /etc/default/tftpd-hpa"
systemctl restart tftpd-hpa.service
echo "restarted tftpd-hpa.service with payload-specific configuration"

# setup freebsd aarch64 rootfs
################################################################################

tar xf $PAYLOADDIR/freebsd-aarch64-rootfs.tar -C $PAYLOADDIR
chmod +x $PAYLOADDIR/riscv-freebsd-boot.sh
mv $PAYLOADDIR/riscv-freebsd-boot.sh $PAYLOADDIR/freebsd-aarch64-rootfs/root/riscv-freebsd-boot/
mv $PAYLOADDIR/virtio.fs $PAYLOADDIR/freebsd-aarch64-rootfs/root/riscv-freebsd-boot/

# setup ganesha configuration
################################################################################
cat << EOF > /tmp/ganesha.conf
LOG {
  Components {
    ALL = NULL;
  }
}
NFS_CORE_PARAM {
  mount_path_pseudo = true;
}
EXPORT {
  Export_id = 12345;
  Path = ${PAYLOADDIR}/freebsd-aarch64-rootfs;
  Pseudo = {{ nfs_export_pseudo }};
  Protocols = 3;
  Access_Type = RW;
  #Squash = root_squash;
  #Sectype = sys;
  FSAL {
    Name = VFS;
  }
  CLIENT {
    Clients = {{ nfs_export_clients }};
    Squash = None;
  }
}
EOF
echo "generated /tmp/ganesha.conf"
mount --bind -o ro ${PAYLOADDIR}/conf/ganesha.conf /etc/ganesha/ganesha.conf
echo "bound mounted ${PAYLOADDIR}/conf/ganesha.conf over /etc/ganesha/ganesha.conf"
systemctl restart nfs-ganesha.service
echo "restarted nfs-ganesha.service with payload-specific configuration"

# stratix10 boot
################################################################################
QUARTUS_BINDIR=/opt/intelFPGA_pro/23.3/qprogrammer/quartus/bin
QUARTUS_PGM=$QUARTUS_BINDIR/quartus_pgm
($QUARTUS_PGM -m jtag -o P\;${PAYLOADDIR}/tftp/fpga.hps.rbf@1 || \
 $QUARTUS_PGM -m jtag -o P\;${PAYLOADDIR}/tftp/fpga.hps.rbf@2)
if [ $? ]; then
{% if interactive %}
expect -c 'log_user 1' \
       -c 'set timeout -1' \
       -c 'spawn picocom -b 115200 /dev/ttyACM0' \
       -c 'interact'
{% else %}
expect -c 'log_user 1' \
       -c 'set timeout -1' \
       -c 'spawn picocom -b 115200 /dev/ttyACM0' \
       -c 'expect "EXPECT >> HPS >> DONE"' \
       -c 'exit 0'

sleep 20 # Allow HPS to shutdown
sync

# terminate runme payload script
################################################################################

systemctl stop nfs-ganesha.service
umount /etc/ganesha/ganesha.conf
echo "nfs-ganesha stopped and bound mounted config unmounted"
systemctl stop tftp-hpa.service
umount /etc/default/tftpd-hpa
echo "nfs-ganesha stopped and bound mounted config unmounted"
echo "payload over, shutting down"
shutdown -h now
{% endif %}
fi
