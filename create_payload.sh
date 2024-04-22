#! /usr/bin/env sh

EXTRA_SPACE=0
MIN_SIZE=$(numfmt --from=iec 512M)
PAYLOAD_IMG=`pwd`"/de10playground_payload.img"
PAYLOAD_LABEL="DE10PGNDPLD"
#PAYLOAD_LABEL="de10playground_payload"


# Function to display script usage
usage() {
  echo "Usage: $0 [OPTIONS] PAYLOAD_DIR"
  echo "Options:"
  echo " -h     Display this help message"
  echo " -s NUM Required extra space (default: $EXTRA_SPACE)"
}

# "entry point" of the script
# first, get command line flags
while getopts "hs:" flag; do
  #echo "seen flag $flag with option $OPTARG"
  case $flag in
    h)
    usage
    exit 0
    ;;
    s) # required extra space
    EXTRA_SPACE=$(numfmt --from=iec $OPTARG)
    ;;
    \?)
    echo "unknown option $flag"
    usage
    exit 1
    ;;
  esac
done
shift $((OPTIND -1))

PAYLOAD_DIR=$1
if [ -z "$PAYLOAD_DIR" ]; then
  echo "no directory provided"
  exit 1
elif ! [ -d "$PAYLOAD_DIR" ]; then
  echo "provided directory '$PAYLOAD_DIR' does not exist"
  exit 1
fi
IMG_SIZE=$(du --bytes --summarize --total $PAYLOAD_DIR | cut -f1 | tail -n1)
test EXTRA_SPACE && IMG_SIZE=$(($IMG_SIZE+$EXTRA_SPACE))
IMG_SIZE=$(( $IMG_SIZE > $MIN_SIZE ? $IMG_SIZE : $MIN_SIZE ))

truncate -s $IMG_SIZE $PAYLOAD_IMG
mkfs.ext4 -L $PAYLOAD_LABEL $PAYLOAD_IMG
#mkfs.vfat -n $PAYLOAD_LABEL $PAYLOAD_IMG
#mkfs.exfat -L $PAYLOAD_LABEL $PAYLOAD_IMG
TMP_MNTDIR=$(mktemp -d)
fuseext2 -o rw+ $PAYLOAD_IMG $TMP_MNTDIR
#fusefat -o rw+ $PAYLOAD_IMG $TMP_MNTDIR
#exfat-fuse -o rw+ $PAYLOAD_IMG $TMP_MNTDIR
cp -r $PAYLOAD_DIR/* $TMP_MNTDIR
fusermount -u $TMP_MNTDIR
rm -r $TMP_MNTDIR
