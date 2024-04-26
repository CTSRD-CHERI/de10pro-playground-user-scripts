#! /usr/bin/env sh

EXTRA_SPACE=0
FS_FMT='ext4'
MIN_SIZE=$(numfmt --from=iec 512M)
PAYLOAD_LABEL="DE10PGNDPLD"
#PAYLOAD_LABEL="de10playground_payload"


# Function to display script usage
usage() {
  echo "Usage: $0 [OPTIONS] PAYLOAD_DIR"
  echo "Options:"
  echo " -h      Display this help message"
  echo " -s NUM  Required extra space (default: $EXTRA_SPACE)"
  echo " -f FMT  Desired filesystem format, one of 'ext4' or 'fat' (deafult: ext4)"
  echo " -o NAME Desired output file name"
}

# "entry point" of the script
# first, get command line flags
while getopts "hs:f:o:" flag; do
  #echo "seen flag $flag with option $OPTARG"
  case $flag in
    h)
    usage
    exit 0
    ;;
    s) # required extra space
    EXTRA_SPACE=$(numfmt --from=iec $OPTARG)
    ;;
    f) # desired filesystem format
    case $OPTARG in
      ext4)
      FS_FMT='ext4'
      ;;
      fat)
      FS_FMT='fat'
      ;;
      \?)
      echo "unknown $flag option $OPTARG"
      exit 1
      ;;
    esac
    ;;
    o)
    PAYLOAD_IMG=$OPTARG
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

TMP_MNTDIR=$(mktemp -d)
[ -z ${PAYLOAD_IMG+x} ] && PAYLOAD_IMG=`pwd`"/de10playground_payload.img"
truncate -s $IMG_SIZE $PAYLOAD_IMG
case $FS_FMT in
  ext4)
  mkfs.ext4 -L $PAYLOAD_LABEL $PAYLOAD_IMG
  fuseext2 -o rw+ $PAYLOAD_IMG $TMP_MNTDIR
  ;;
  fat)
  mkfs.vfat -n $PAYLOAD_LABEL $PAYLOAD_IMG
  fusefat -o rw+ $PAYLOAD_IMG $TMP_MNTDIR
  #mkfs.exfat -L $PAYLOAD_LABEL $PAYLOAD_IMG
  #exfat-fuse -o rw+ $PAYLOAD_IMG $TMP_MNTDIR
  ;;
esac
cp -r $PAYLOAD_DIR/* $TMP_MNTDIR
fusermount -u $TMP_MNTDIR
rm -r $TMP_MNTDIR
