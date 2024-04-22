#! /usr/bin/env sh

PAYLOADDIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

echo "HPS boot payload"

# setup tftpd configuration
################################################################################

cat << EOF > /tmp/tftpd-hpa
TFTP_USERNAME="tftp"
TFTP_DIRECTORY="${PAYLOADDIR}/tftp"
TFTP_ADDRESS=":69"
TFTP_OPTIONS="--secure"
EOF
echo "generated /tmp/tftpd-hpa"
mount --bind -o ro /tmp/tftpd-hpa /etc/default/tftpd-hpa
echo "bound mounted /tmp/tftpd-hpa over /etc/default/tftpd-hpa"
systemctl restart tftpd-hpa.service
echo "restarted tftpd-hpa.service with payload-specific configuration"

# setup ganesha configuration
################################################################################

tar xf $PAYLOADDIR/freebsd-aarch64-rootfs.tar -C $PAYLOADDIR

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
  Pseudo = /freebsd-aarch64-rootfs;
  Protocols = 3;
  Access_Type = RW;
  #Squash = root_squash;
  #Sectype = sys;
  FSAL {
    Name = VFS;
  }
  CLIENT {
    Clients = 192.168.0.10/24;
    Squash = None;
  }
}
EOF
echo "generated /tmp/ganesha.conf"
mount --bind -o ro /tmp/ganesha.conf /etc/ganesha/ganesha.conf
echo "bound mounted /tmp/ganesha.conf over /etc/ganesha/ganesha.conf"
systemctl restart nfs-ganesha.service
echo "restarted nfs-ganesha.service with payload-specific configuration"

# stratix10 boot
################################################################################
QUARTUS_BINDIR=/opt/intelFPGA_pro/23.3/qprogrammer/quartus/bin
QUARTUS_PGM=$QUARTUS_BINDIR/quartus_pgm
($QUARTUS_PGM -m jtag -o P\;${PAYLOADDIR}/tftp/fpga.hps.rbf@1 || \
 $QUARTUS_PGM -m jtag -o P\;${PAYLOADDIR}/tftp/fpga.hps.rbf@2) && \
expect -c 'log_user 1' \
       -c 'set timeout -1' \
       -c 'spawn picocom -b 115200 /dev/ttyACM0' \
       -c 'expect "EXPECT >> HPS SYSTEM BOOT DONE"' \
       -c 'exit 0'

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
