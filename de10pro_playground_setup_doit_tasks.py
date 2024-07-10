import os
import sys
import yaml
import shutil
import jinja2
import tempfile
import subprocess
import urllib.request

def init_ctxt( template_directory = 'templates'
             , template_parameters = 'template-parameters.yaml'
             , output_directory = 'setup_output' ):

  global tmpl_env
  global tmpl_params
  global outdir

  tmpl_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_directory))

  tmpl_params = {k: {} for k in tmpl_env.list_templates()}
  with open(template_parameters, mode='r') as f:
    tmpl_params = yaml.safe_load(f)

  outdir = output_directory

init_ctxt()

def require_cmd(cmd):
  if shutil.which(cmd) is None:
    print(f'\n/!\\ "{cmd}" is not available /!\\\n', file=sys.stderr)
    exit(1)

def task_get_freebsd_aarch64_rootfs():
  def get_freebsd_aarch64_rootfs():
    os.makedirs(outdir, exist_ok=True)
    subprocess.run([ 'rsync'
                   , 'caravel.cl.cam.ac.uk:/auto/anfs/bigdisc/aj443/de10pro-playground/freebsd-aarch64-rootfs.tar'
                   , f'{outdir}/freebsd-aarch64-rootfs.raw.tar' ])
  return {
    'actions': [get_freebsd_aarch64_rootfs]
  , 'targets': [f'{outdir}/freebsd-aarch64-rootfs.raw.tar']
  , 'uptodate': [True]
  }

def task_gen_ssh_keys():
  def gen_keys():
    with tempfile.TemporaryFile("w+") as f:
      f.write('y')
      subprocess.run([ 'ssh-keygen', '-N', '""', '-f', f'{outdir}/key' ], stdin=f)
  return {
    'actions': [gen_keys]
  , 'targets': [f'{outdir}/key', f'{outdir}/key.pub']
  , 'uptodate': [True]
  }

def task_install_aarch64_rootfs_ssh_keys():
  d = outdir
  def install_keys():
    os.makedirs(d, exist_ok=True)
    shutil.copy( f'{d}/freebsd-aarch64-rootfs.raw.tar'
               , f'{d}/freebsd-aarch64-rootfs.tar' )
    subprocess.run(['tar', '--delete', '-f', f'{d}/freebsd-aarch64-rootfs.tar'
                                           , f'{d}/freebsd-aarch64-rootfs/root/.ssh'])
    os.makedirs(f'{d}/freebsd-aarch64-rootfs/root/.ssh', exist_ok=True)
    shutil.copy(f'{d}/key.pub', f'{d}/freebsd-aarch64-rootfs/root/.ssh/authorized_keys')
    shutil.copy(f'{d}/key.pub', f'{d}/freebsd-aarch64-rootfs/root/.ssh/key.pub')
    shutil.copy(f'{d}/key', f'{d}/freebsd-aarch64-rootfs/root/.ssh/key')
    subprocess.run(['tar', '-rvf', f'{d}/freebsd-aarch64-rootfs.tar'
                                 , f'{d}/freebsd-aarch64-rootfs/root/.ssh'])
  return {
    'actions': [install_keys]
  , 'file_dep': [f'{d}/key', f'{d}/key.pub', f'{d}/freebsd-aarch64-rootfs.raw.tar']
  , 'targets': [f'{d}/freebsd-aarch64-rootfs.tar']
  }

def task_get_aarch64_bsd_loader():
  url = 'https://www.cl.cam.ac.uk/~jdw57/loader.efi'
  loader = f'{outdir}/payload/tftp/loader.efi'
  def get_loader():
    os.makedirs(f'{outdir}/payload/tftp/', exist_ok=True)
    urllib.request.urlretrieve(url, filename=loader)
  return {
    'actions': [get_loader]
  , 'targets': [loader]
  , 'uptodate': [True]
  }

def task_get_bitfiles():
  d = f'{outdir}/payload/tftp'
  hps_rbf = f'{d}/fpga.hps.rbf'
  core_rbf = f'{d}/fpga.core.rbf'
  path = "caravel.cl.cam.ac.uk:/auto/anfs/bigdisc/de10pro-playground/aj443/"
  def get_bitfiles():
    os.makedirs(d, exist_ok=True)
    subprocess.run(['rsync', f'{path}/fpga.hps.rbf', hps_rbf])
    subprocess.run(['rsync', f'{path}/fpga.core.rbf', core_rbf])
  return {
    'actions': [get_bitfiles]
  , 'targets': [hps_rbf, core_rbf]
  , 'uptodate': [True]
  }

def task_gen_uboot_stage2():
  t = tmpl_env.get_template('tftp/u-boot-stage2.cmd')
  out_fname = f'{outdir}/payload/tftp/u-boot-stage2.scr'
  def gen_uboot_stage2():
    r = t.render(**(tmpl_params['tftp/u-boot-stage2.cmd']))
    os.makedirs(f'{outdir}/payload/tftp', exist_ok=True)
    with tempfile.NamedTemporaryFile('w') as f:
      f.write(r)
      f.flush()
      require_cmd('mkimage')
      subprocess.run(['mkimage', '-T', 'script', '-d', f.name, out_fname])
  return {
    'actions': [gen_uboot_stage2]
  , 'file_dep': [t.filename]
  , 'targets': [out_fname]
  }

def task_get_socfpga_stratix10_dtb():
  url = 'https://www.cl.cam.ac.uk/~aj443/socfpga_stratix10_de10_pro.dts.dtb'
  dtb = f'{outdir}/payload/tftp/socfpga_stratix10_de10_pro.dts.dtb'
  def get_dtb():
    os.makedirs(f'{outdir}/payload/tftp', exist_ok=True)
    urllib.request.urlretrieve(url, filename=dtb)
  return {
    'actions': [get_dtb]
  , 'targets': [dtb]
  , 'uptodate': [True]
  }

#def task_gen_nfs_conf():
#  t = tmpl_env.get_template('conf/ganesha.conf')
#  out_fname = f'{outdir}/payload/conf/ganesha.conf'
#  def gen_nfs_conf():
#    r = t.render(**(tmpl_params['conf/ganesha.conf']))
#    os.makedirs(f'{outdir}/payload/conf', exist_ok=True)
#    with open(out_fname, mode='w') as f:
#      f.write(r)
#  return {
#    'actions': [gen_nfs_conf]
#  , 'file_dep': [t.filename]
#  , 'targets': [out_fname]
#  }

#def task_gen_tftp_conf():
#  t = tmpl_env.get_template('conf/tftpd-hpa')
#  out_fname = f'{outdir}/payload/conf/tftpd-hpa'
#  def gen_tftp_conf():
#    r = t.render(**(tmpl_params['conf/tftpd-hpa']))
#    os.makedirs(f'{outdir}/payload/conf', exist_ok=True)
#    with open(out_fname, mode='w') as f:
#      f.write(r)
#  return {
#    'actions': [gen_tftp_conf]
#  , 'file_dep': [t.filename]
#  , 'targets': [out_fname]
#  }

def task_gen_payload_runme():
  t = tmpl_env.get_template('runme.sh')
  out_fname = f'{outdir}/payload/runme.sh'
  def gen_runme():
    r = t.render(**(tmpl_params['runme.sh']))
    os.makedirs(f'{outdir}/payload', exist_ok=True)
    with open(out_fname, mode='w') as f:
      f.write(r)
    os.chmod(out_fname, 0o544)
  return {
    'actions': [gen_runme]
  , 'file_dep': [t.filename]
  , 'targets': [out_fname]
  }

def task_create_payload():
  d = f'{outdir}'
  pd = f'{d}/payload'
  fdeps = [
    f'{pd}/runme.sh'
  #, f'{pd}/conf/tftpd-hpa'
  #, f'{pd}/conf/ganesha.conf'
  , f'{pd}/tftp/loader.efi'
  , f'{pd}/tftp/socfpga_stratix10_de10_pro.dts.dtb'
  , f'{pd}/tftp/u-boot-stage2.scr'
  , f'{pd}/tftp/fpga.hps.rbf'
  , f'{pd}/tftp/fpga.core.rbf'
  ]
  def create_payload():
    require_cmd('fuseext2')
    subprocess.run([ './create_payload.sh', '-s', '14G'
                   , '-o', f'{d}/de10playground_payload.img', pd ])
  return {
    'actions': [create_payload]
  , 'file_dep': fdeps
  , 'targets': [f'{d}/de10playground_payload.img']
  }

def task_get_ubuntu_cloud_image():
  vm_img = f'{outdir}/de10pro-playground-vm.qcow2'
  ubuntu_img_url="https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
  def get_img():
    tmp, _ = urllib.request.urlretrieve(ubuntu_img_url)
    shutil.move(tmp, vm_img)
  return {
    'actions': [get_img]
  , 'targets': [vm_img]
  , 'uptodate': [True]
  }

def task_gen_cloud_init_conf():
  t0 = tmpl_env.get_template('vm-cloud-init/user-data')
  t1 = tmpl_env.get_template('vm-cloud-init/user-data')
  d = f'{outdir}/vm-cloud-init'
  out_fname0 = f'{d}/user-data'
  out_fname1 = f'{d}/meta-data'
  def gen_cloud_init_conf():
    sshkey = {'name': 'key'}
    with open(f'{outdir}/key','r') as key: sshkey['priv'] = key.read()
    with open(f'{outdir}/key.pub','r') as pkey: sshkey['pub'] = pkey.read()
    tmpl_params['vm-cloud-init/user-data'] = {'sshkeys': [sshkey]}
    os.makedirs(d, exist_ok=True)
    r = t0.render(**(tmpl_params['vm-cloud-init/user-data']))
    with open(out_fname0, mode='w') as f: f.write(r)
    tmpl_params['vm-cloud-init/meta-data'] = {}
    r = t1.render(**(tmpl_params['vm-cloud-init/meta-data']))
    with open(out_fname1, mode='w') as f: f.write(r)
  return {
    'actions': [gen_cloud_init_conf]
  , 'file_dep': [t0.filename, t1.filename, f'{outdir}/key', f'{outdir}/key.pub']
  , 'targets': [out_fname0, out_fname1]
  }

def task_gen_cloud_init_iso():
  userdata = f'{outdir}/vm-cloud-init/user-data'
  metadata = f'{outdir}/vm-cloud-init/meta-data'
  isoname = f'{outdir}/vm-cloud-init/config.iso'
  def gen_cloud_init_iso():
    with open(isoname, 'w') as _:
      require_cmd('mkisofs')
      subprocess.run([ 'mkisofs', '--output', isoname
                     , '-volid', 'cidata', '-joliet', '-rock'
                     , userdata, metadata ])
  return {
    'actions': [gen_cloud_init_iso]
  , 'file_dep': [ f'{outdir}/vm-cloud-init/user-data'
                , f'{outdir}/vm-cloud-init/meta-data'
                ]
  , 'targets': [isoname]
  }

def task_gen_vm_image():
  vmimage = f'{outdir}/de10pro-playground-user-vm.qcow2'
  def gen_vm_image():
    shutil.copy(f'{outdir}/de10pro-playground-vm.qcow2', vmimage)
    require_cmd('qemu-img')
    subprocess.run(['qemu-img', 'resize', vmimage, '16G'])
    subprocess.run([ 'qemu-system-x86_64', '-enable-kvm', '-m', '2048'
                   , '-machine', 'q35'
                   , '-drive', f'file={vmimage},if=virtio'
                   , '-drive', f'driver=raw,file={outdir}/vm-cloud-init/config.iso,if=virtio'
                   , '-nographic' ])
  return {
    'actions': [gen_vm_image]
  , 'file_dep': [ f'{outdir}/de10pro-playground-vm.qcow2'
                , f'{outdir}/vm-cloud-init/config.iso'
                ]
  , 'targets': [vmimage]
  }

def task_run_vm():
  def run_vm():
    subprocess.run([ '/opt/de10playground/bin/de10playground'
                   , f'{outdir}/de10pro-playground-user-vm.qcow2'
                   , f'{outdir}/de10playground_payload.img' ])
  return {
    'actions': [run_vm]
  , 'file_dep': [ f'{outdir}/de10pro-playground-user-vm.qcow2'
                , f'{outdir}/de10playground_payload.img' ]
  }
