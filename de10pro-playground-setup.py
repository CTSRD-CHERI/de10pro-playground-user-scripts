#! /usr/bin/env python3

import urllib.request
import subprocess
import datetime
import tempfile
import argparse
import pathlib
import shutil
import jinja2
import yaml
import sys
import os

def require_cmd(cmd):
  if shutil.which(cmd) is None:
    print(f'\n/!\\ "{cmd}" is not available /!\\\n', file=sys.stderr)
    exit(1)

def gen_vm_image( cloud_init_user_data, cloud_init_meta_data
                , ubuntu_img_url="https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
                ,):
  print('generate-vm-image')
  vm_img, _ = urllib.request.urlretrieve(ubuntu_img_url)
  require_cmd('qemu-img')
  subprocess.run(['qemu-img', 'resize', vm_img, '16G'])
  with tempfile.NamedTemporaryFile() as cloud_init_iso:
    require_cmd('mkisofs')
    subprocess.run([ 'mkisofs', '--output', cloud_init_iso.name
                   , '-volid', 'cidata', '-joliet', '-rock'
                   , cloud_init_user_data, cloud_init_meta_data ])
    subprocess.run([ 'qemu-system-x86_64', '-enable-kvm', '-m', '2048'
                   , '-machine', 'q35'
                   , '-drive', f'file={vm_img},if=virtio'
                   , '-drive', f'driver=raw,file={cloud_init_iso.name},if=virtio'
                   , '-nographic' ])
  shutil.move(vm_img, f'{clargs.output_path}/{clargs.vm_image_name}')

def gen_arm_rootfs():
  #subprocess.run([ 'rsync', 'choisi.cl.cam.ac.uk:/auto/anfs/bigdisc/aj443/freebsd-aarch64-rootfs.tar', './freebsd-aarch64-rootfs.tar'])
  pass

def setup_keys():
  subprocess.run([ 'rm', '-rf', 'key*'])
  subprocess.run([ 'ssh-keygen', '-N', '""', '-f', 'key' ])
  subprocess.run([ 'tar', '--delete', '-f', 'freebsd-aarch64-rootfs.tar', 'freebsd-aarch64-rootfs/root/.ssh' ])
  os.makedirs('freebsd-aarch64-rootfs/root/.ssh', exist_ok=True)
  shutil.copy('key.pub', 'freebsd-aarch64-rootfs/root/.ssh/authorized_keys')
  shutil.move('key.pub', 'freebsd-aarch64-rootfs/root/.ssh/key.pub')
  shutil.move('key', 'freebsd-aarch64-rootfs/root/.ssh/key')
  subprocess.run([ 'tar', '-rvf', 'freebsd-aarch64-rootfs.tar', 'freebsd-aarch64-rootfs/root/.ssh' ])

def create_payload_runme():
  with open("runme.sh", "w") as f:
    f.write('''#! /usr/bin/env sh

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
#chmod +x $PAYLOADDIR/riscv-freebsd-boot.sh
#mv $PAYLOADDIR/riscv-freebsd-boot.sh $PAYLOADDIR/freebsd-aarch64-rootfs/root/riscv-freebsd-boot/
#mv $PAYLOADDIR/virtio.fs             $PAYLOADDIR/freebsd-aarch64-rootfs/root/riscv-freebsd-boot/
rm $PAYLOADDIR/freebsd-aarch64-rootfs/root/riscv-freebsd-boot/riscv-freebsd-boot.sh

chown root:root $PAYLOADDIR/freebsd-aarch64-rootfs/root/.ssh/*
echo "ls freebsd-aarch64-rootfs/root/.ssh"
ls -l $PAYLOADDIR/freebsd-aarch64-rootfs/root/.ssh/

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
       -c 'expect "EXPECT >> HPS >> DONE"' \
       -c 'interact'

    ''')


def boot_de10():
  gen_arm_rootfs()
  setup_keys()
  create_payload_runme()
  with tempfile.NamedTemporaryFile(mode='w+') as boot_de10:
    boot_de10.write('''
      rm -rf payload_hps-boot
      mkdir -p payload_hps-boot
      mkdir -p payload_hps-boot/tftp
      #tar xf freebsd-aarch64-rootfs.tar --directory=payload_hps-boot
      # XXX the freebsd-aarch64-rootfs.tar is currently copied from a one-off archived artifact job
      # XXX TODO: it should really be properly generated
      # grab the rbf files (these are currently copied from a jenkins job that builds them)
      cp output_files/*.hps.rbf payload_hps-boot/tftp/fpga.hps.rbf
      cp output_files/*.core.rbf payload_hps-boot/tftp/fpga.core.rbf
      
      # prepare benchmark image for riscv
      #rm -rf benches/cheri
      #mkdir benches/cheri
      #mv benches/*purecap.tar.xz benches/cheri/
      #rm -rf benches/riscv
      #mkdir benches/riscv
      #mv benches/*riscv64.tar.xz benches/riscv/
      #cd benches/cheri && tar -xf *.tar.xz && rm *.tar.xz && cd ../..
      #cd benches/riscv && tar -xf *.tar.xz && rm *.tar.xz && cd ../..
      #rm -rf spec2006_riscv
      #mkdir spec2006_riscv && mv spec2006*riscv64.tar.xz spec2006_riscv/
      #cp cheri-evaluation/202203-riscv-spec2006/* spec2006_riscv/
      #cd spec2006_riscv && tar -xf *.tar.xz && rm *.tar.xz && sh preparespecint.sh && cd ../
      #rm -rf spec2006_cheri
      #mkdir spec2006_cheri && mv spec2006*purecap.tar.xz spec2006_cheri/
      #cp cheri-evaluation/202203-riscv-spec2006/* spec2006_cheri/
      #cd spec2006_cheri && tar -xf *.tar.xz && rm *.tar.xz && sh preparespecint.sh && cd ../
      #mv benches virtio/
      #mv spec2006_riscv virtio/
      #mv spec2006_cheri virtio/
      
      #du -h -s virtio
      #./create_payload.sh -f fat -s 100M -o payload_hps-boot/virtio.fs virtio
      
      # TODO: this should not come from Jon's public html space
      curl https://www.cl.cam.ac.uk/~jdw57/loader.efi --output payload_hps-boot/tftp/loader.efi
      #curl https://www.cl.cam.ac.uk/~jdw57/runme.sh --output payload_hps-boot/runme.sh
      cp freebsd*.tar payload_hps-boot/
      cp runme.sh payload_hps-boot/
      chmod +x payload_hps-boot/runme.sh
      mkdir payload_hps-boot/tftp
      cp templates/tftp/u-boot-stage2.scr payload_hps-boot/tftp/
      # TODO: this should not come from Alexandre's public html space
      curl https://www.cl.cam.ac.uk/~aj443/socfpga_stratix10_de10_pro.dts.dtb --output payload_hps-boot/tftp/socfpga_stratix10_de10_pro.dts.dtb
      
      # actually create the payload disk image
      ./create_payload.sh -s 14G payload_hps-boot
      # run the de10pro playground script with the vm image and the payload
      /opt/de10playground/bin/de10playground $1 de10playground_payload.img
    ''')
    boot_de10.flush()
    subprocess.run(['cat', boot_de10.name])
    subprocess.run(['sh', boot_de10.name, 'output/de10pro-playground-vm'])

def report(params={}, comment_pfx='#'):
  rpt=[]
  rpt.append(f'{comment_pfx} file generated by {pathlib.Path(__file__).name}')
  rpt.append(f'{comment_pfx} (https://github.com/CTSRD-CHERI/de10pro-playground-user-scripts.git)')
  rpt.append(f'{comment_pfx} {datetime.datetime.now()}')
  rpt.append(f'{comment_pfx} template file rendered with parameters:')
  for k, v in params.items(): rpt.append(f'{comment_pfx} {k} = {v}')
  return '\n'.join(rpt)

def main_process(tmpl_env, tmpl_params, clargs):

  # always render templates
  #if clargs.subcmd == 'render-templates':
  # run through each templates in the given template parameter configurations
  # and generate the parameterized render
  for t, ps in tmpl_params.items():
    if ps is None:
      shutil.copy(f'templates/{t}', f'{clargs.output_path}/{t}')
      continue
    lines = tmpl_env.get_template(t).render(**ps).split('\n')
    if lines[0][0:2] == '#!':
      lines.insert(1, '\n'+report(ps))
    else:
      lines.insert(0, report(ps)+'\n')
    r = '\n'.join(lines)
    with open(f'{clargs.output_path}/{t}', mode='w') as f: f.write(r)

  if clargs.subcmd == 'generate-vm-image':
    gen_vm_image( f'{clargs.output_path}/vm-cloud-init/user-data'
                , f'{clargs.output_path}/vm-cloud-init/meta-data' )
  if clargs.subcmd == 'boot-de10':
    boot_de10()

if __name__ == '__main__':

  # command line arguments
  parser = argparse.ArgumentParser(description='setup de10pro playground files')
  subparsers = parser.add_subparsers(
    dest='subcmd'
  , help='sub-command (run with -h on a specific sub-command for further help)' )

  # general, common options
  parser.add_argument(
    '--template-parameters', metavar='YAML_TEMPLATE_PARAMETERS'
  , help="The YAML_TEMPLATE_PARAMETERS yaml file with the jinja template parameters to use")
  parser.add_argument(
    '-o', '--output-path', metavar='OUT_PATH', default='./output'
  , help='The OUT_PATH path to the output directory' )

  common_parser = argparse.ArgumentParser(add_help=False)
  # render templates clarg parser
  templ_render_parser = subparsers.add_parser(
    'render-templates', parents=[common_parser], help='Render jinja templates' )

  # generate a VM image
  vm_image_parser = subparsers.add_parser(
    'generate-vm-image', parents=[common_parser], help='Generate a vm image' )
  vm_image_parser.add_argument(
    '-n', '--vm-image-name', metavar='VM_NAME', default='de10pro-playground-vm'
  , help='The VM_NAME name to give to the vm image' )

  boot_parser = subparsers.add_parser(
    'boot-de10', parents=[common_parser], help='Boot de10 using vm image and sofs in output_files.' )
  #boot_parser.add_argument(
  #  '-s', '--sof-directory', metavar='SOF_DIR', default='output_files'
  #, help='The SOF_DIR from which to copy *.hps.sof and *.core.sof' )

  # parse command line arguments
  clargs=parser.parse_args()

  # prepare templates and parameters
  tmpl_env = jinja2.Environment(loader=jinja2.FileSystemLoader('templates/'))
  tmpl_params = {k: {} for k in tmpl_env.list_templates()}
  if hasattr(clargs, 'template_parameters') \
     and clargs.template_parameters is not None:
    with open(clargs.template_parameters, mode='r') as f:
      tmpl_params = yaml.safe_load(f)

  # ensure output folders exists
  os.makedirs(clargs.output_path, exist_ok=True)
  for p in map(pathlib.Path, tmpl_params.keys()):
    os.makedirs(f'{clargs.output_path}/{p.parent}', exist_ok=True)

  # there must be a sub-command
  if not hasattr(clargs, 'subcmd') or clargs.subcmd is None:
    print('\n/!\\ No sub-command was passed /!\\\n', file=sys.stderr)
    parser.print_help(sys.stderr)
    sys.exit(1)

  main_process(tmpl_env, tmpl_params, clargs)
