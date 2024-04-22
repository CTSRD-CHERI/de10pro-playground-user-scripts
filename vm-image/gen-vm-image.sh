#! /usr/bin/env sh

WORKDIR=$(pwd)
VMIMAGEDIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

curl https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img --output $WORKDIR/de10pro-playground-$USER-vm.qcow2
qemu-img resize $WORKDIR/de10pro-playground-$USER-vm.qcow2 16G
ISO_IMG=$(mktemp /tmp/XXXXXX.iso)
mkisofs --output $ISO_IMG -volid cidata -joliet -rock $VMIMAGEDIR/cloud-init/user-data $VMIMAGEDIR/cloud-init/meta-data
kvm -m 2048 -machine q35 -drive file=$WORKDIR/de10pro-playground-$USER-vm.qcow2,if=virtio -drive driver=raw,file=$ISO_IMG,if=virtio -nographic
rm $ISO_IMG
