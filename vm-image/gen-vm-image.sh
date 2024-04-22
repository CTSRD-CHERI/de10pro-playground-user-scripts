curl -C- -O https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img
mv jammy-server-cloudimg-amd64.img jammy-server-cloudimg-amd64.qcow2
qemu-img resize jammy-server-cloudimg-amd64.qcow2 32G
mkisofs --output cloud-init/seed.iso -volid cidata -joliet -rock cloud-init/user-data cloud-init/meta-data
kvm -m 2048 -machine q35 -drive file=jammy-server-cloudimg-amd64.qcow2,if=virtio -drive driver=raw,file=cloud-init/seed.iso,if=virtio -nographic
