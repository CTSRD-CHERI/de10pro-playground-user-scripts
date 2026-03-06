import os
import sys
import yaml
import shutil
import jinja2
import textwrap
import tempfile
import subprocess
import urllib.request
from pathlib import Path

def init_ctxt( template_directory = 'templates'
             , template_parameters = 'template-parameters.yaml'
             , output_directory = 'setup_output'
             , hps_rbf = Path("caravel.cl.cam.ac.uk:/auto/anfs/bigdisc/aj443/de10pro-playground/fpga.hps.rbf")
             , core_rbf = Path("caravel.cl.cam.ac.uk:/auto/anfs/bigdisc/aj443/de10pro-playground/fpga.core.rbf")
             , hps_uboot = Path("u-boot-socfpga/u-boot-dtb.bin")
             , payload = None
             , param_libguestfs_debug_trace = False
             , param_supermin_kernel = "/opt/de10playground/supermin_libguestfs_kernel"
             ):
  global tmpl_env
  global tmpl_params
  global outdir
  global builddir
  global pd
  global bitfiles
  global libguestfs_debug_trace
  global supermin_kernel
  global hps_uboot_file

  tmpl_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_directory))

  tmpl_params = {k: {} for k in tmpl_env.list_templates()}
  with open(template_parameters, mode='r') as f:
    tmpl_params = yaml.safe_load(f)

  outdir = Path(output_directory)
  builddir = outdir / 'build'
  pd = Path(payload) if payload else outdir / 'de10playground-payload'

  bitfiles = (hps_rbf, core_rbf)
  extra_payload = payload
  libguestfs_debug_trace = param_libguestfs_debug_trace
  supermin_kernel = param_supermin_kernel
  hps_uboot_file = hps_uboot

init_ctxt()

def require_cmd(cmd):
  if shutil.which(cmd) is None:
    print(f'\n/!\\ "{cmd}" is not available /!\\\n', file=sys.stderr)
    exit(1)

def task_gen_ssh_keys():
  def gen_keys():
    with tempfile.TemporaryFile("w+") as f:
      f.write('y')
      subprocess.run([ 'ssh-keygen', '-N', '', '-f', f'{outdir}/key' ], stdin=f)
  return {
    'actions': [gen_keys]
  , 'targets': [f'{outdir}/key', f'{outdir}/key.pub']
  , 'uptodate': [True]
  }

def task_get_aarch64_bsd_loader():
  url = 'https://www.cl.cam.ac.uk/~jdw57/loader.efi'
  loader = f'{pd}/tftp/loader.efi'
  def get_loader():
    (pd / 'tftp').mkdir(parents = True, exist_ok = True)
    urllib.request.urlretrieve(url, filename=loader)
  return {
    'actions': [get_loader]
  , 'targets': [loader]
  , 'uptodate': [True]
  }

def task_get_bitfiles():
  hps_rbf = f'{pd}/tftp/fpga.hps.rbf'
  core_rbf = f'{pd}/tftp/fpga.core.rbf'
  def get_bitfiles():
    (pd / 'tftp').mkdir(parents = True, exist_ok = True)
    subprocess.run(['rsync', '-L', bitfiles[0], hps_rbf])
    subprocess.run(['rsync', '-L', bitfiles[1], core_rbf])
  return {
    'actions': [get_bitfiles]
  , 'targets': [hps_rbf, core_rbf]
  , 'uptodate': [True]
  }

def task_get_hps_uboot():
  uboot_bin = pd / 'tftp/u-boot-dtb.bin'
  def copy_hps_uboot():
    shutil.copy(hps_uboot_file, uboot_bin)
  return {
    'actions': [copy_hps_uboot]
  , 'targets': [uboot_bin]
  , 'uptodate': [True]
  , 'verbosity': 2
  }

def task_gen_uboot_stage2():
  t = tmpl_env.get_template('tftp/u-boot-stage2.cmd')
  out_fname = f'{pd}/tftp/u-boot-stage2.scr'
  def gen_uboot_stage2():
    r = t.render(**(tmpl_params['tftp/u-boot-stage2.cmd']))
    (pd / 'tftp').mkdir(parents = True, exist_ok = True)
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

def task_gen_hps_openocd_cfg():
  t = tmpl_env.get_template('hps.a53.openocd.cfg')
  out_fname = f'{pd}/hps.a53.openocd.cfg'
  def gen_hps_openocd_cfg():
    tmpl_params['hps.a53.openocd.cfg'] = {}
    r = t.render(**(tmpl_params['hps.a53.openocd.cfg']))
    pd.mkdir(parents = True, exist_ok = True)
    with open(out_fname, 'w') as f: f.write(r)
  return {
    'actions': [gen_hps_openocd_cfg]
  , 'file_dep': [t.filename]
  , 'targets': [out_fname]
  }

def task_gen_hps_gdb_script():
  t = tmpl_env.get_template('hps.a53.boot.gdb')
  out_fname = f'{pd}/hps.a53.boot.gdb'
  def gen_hps_gdb_script():
    tmpl_params['hps.a53.boot.gdb'] = {}
    r = t.render(**(tmpl_params['hps.a53.boot.gdb']))
    pd.mkdir(parents = True, exist_ok = True)
    with open(out_fname, 'w') as f: f.write(r)
  return {
    'actions': [gen_hps_gdb_script]
  , 'file_dep': [t.filename]
  , 'targets': [out_fname]
  }

def task_gen_bash_profile():
  t = tmpl_env.get_template('.bash_profile')
  out_fname = f'{outdir}/.bash_profile'
  def gen_bash_profile():
    tmpl_params['.bash_profile'] = {}
    r = t.render(**(tmpl_params['.bash_profile']))
    pd.mkdir(parents = True, exist_ok = True)
    with open(out_fname, 'w') as f: f.write(r)
  return {
    'actions': [gen_bash_profile]
  , 'file_dep': [t.filename]
  , 'targets': [out_fname]
  }

def task_get_socfpga_stratix10_dtb():
  url = 'https://www.cl.cam.ac.uk/~aj443/socfpga_stratix10_de10_pro.dts.dtb'
  dtb = f'{pd}/tftp/socfpga_stratix10_de10_pro.dts.dtb'
  def get_dtb():
    (pd / 'tftp').mkdir(parents = True, exist_ok = True)
    urllib.request.urlretrieve(url, filename=dtb)
  return {
    'actions': [get_dtb]
  , 'targets': [dtb]
  , 'uptodate': [True]
  }

def task_gen_payload_runme():
  t = tmpl_env.get_template('runme.sh')
  out_fname = f'{pd}/runme.sh'
  def gen_runme():
    if not os.path.exists(out_fname):
      r = t.render(**(tmpl_params['runme.sh']))
      pd.mkdir(parents = True, exist_ok = True)
      with open(out_fname, mode='w') as f:
        f.write(r)
      os.chmod(out_fname, 0o766)
  return {
    'actions': [gen_runme]
  , 'file_dep': [t.filename]
  , 'targets': [out_fname]
  }

def task_create_user_disk():
  d = Path(outdir)
  fdeps = [
    f'runme.sh'
  , f'hps.a53.openocd.cfg'
  , f'hps.a53.boot.gdb'
  , f'tftp/u-boot-dtb.bin'
  , f'tftp/loader.efi'
  , f'tftp/socfpga_stratix10_de10_pro.dts.dtb'
  , f'tftp/u-boot-stage2.scr'
  , f'tftp/fpga.hps.rbf'
  , f'tftp/fpga.core.rbf'
  ]
  bash_profile = d / f'.bash_profile'
  pubkey = d / f'key.pub'
  tmpmounts = d / 'tmpmounts'
  usr_dsk = d / 'de10playground-user-disk.qcow2'
  usr_dsk_sz = '32G'
  def create_user_disk():
    script = f"qemu-img create -f qcow2 {usr_dsk} {usr_dsk_sz}"
    p0 = subprocess.Popen( [shutil.which('bash'), '--login', '-c', script]
                         , stdout=subprocess.PIPE
                         , stderr=subprocess.STDOUT )
    out0, err0 = p0.communicate()
    p0.wait()
    tmpauthkeys = tempfile.NamedTemporaryFile(mode = 'w')
    tmpauthkeys.write(pubkey.read_text())
    #script = textwrap.dedent(f"""
    script = f"""
    add {usr_dsk}
    run
    part-init /dev/sda gpt
    part-add /dev/sda primary 2048 -2048
    mkfs ext4 /dev/sda1
    mount /dev/sda1 /

    copy-in {pd.absolute()} /
    chown 1000 1000 /{pd.name}

    copy-in {bash_profile.absolute()} /
    chown 1000 1000 /{bash_profile.name}

    mkdir /.ssh
    chown 1000 1000 /.ssh/
    chmod 0700 /.ssh
    copy-in {pubkey.absolute()} /.ssh/
    mv /.ssh/{pubkey.name} /.ssh/authorized_keys
    chown 1000 1000 /.ssh/authorized_keys
    chmod 0600 /.ssh/authorized_keys

    umount /
    exit
    """
    env = os.environ.copy()
    env['TMPDIR'] = tmpmounts
    if libguestfs_debug_trace:
      env['LIBGUESTFS_DEBUG'] = "1"
      env['LIBGUESTFS_TRACE'] = "1"
    #env['LIBGUESTFS_BACKEND'] = "direct"
    env['SUPERMIN_KERNEL'] = supermin_kernel
    tmpmounts.mkdir(parents = True, exist_ok = True)
    (tmpmounts / 'tmp').mkdir(parents = True, exist_ok = True)
    p1 = subprocess.Popen( [shutil.which('guestfish'), '--']
                         , env = env
                         , stdin=subprocess.PIPE
                         , stdout=subprocess.PIPE
                         , stderr=subprocess.STDOUT
                         , text = True )
    out1, err1 = p1.communicate(script)
    print(out0)
    print(err0)
    print(out1)
    print(err1)
    tmpauthkeys.close()
    return (p0.returncode == 0 and p1.returncode == 0)

  return {
    'actions': [create_user_disk]
  , 'file_dep': [bash_profile, pubkey] + [f'{pd}/{x}' for x in fdeps]
  , 'targets': [usr_dsk]
  , 'verbosity': 2
  }

def task_get_ubuntu_cloud_image():
  vm_img = f'{outdir}/de10pro-playground-vm.qcow2'
  #ubuntu_img_url="https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
  ubuntu_img_url="https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"
  #ubuntu_img_url="https://cloud-images.ubuntu.com/plucky/current/plucky-server-cloudimg-amd64.img"
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
    with open(f'{outdir}/key','r') as key: sshkey['priv'] = key.read().replace('\n','\\n')
    with open(f'{outdir}/key.pub','r') as pkey: sshkey['pub'] = pkey.read()
    if not tmpl_params['vm-cloud-init/user-data']:
      tmpl_params['vm-cloud-init/user-data'] = {}
    tmpl_params['vm-cloud-init/user-data']['ssh_keys'] = [sshkey]
    print(f"tmpl_params['vm-cloud-init/user-data']: {tmpl_params['vm-cloud-init/user-data']}")
    os.makedirs(d, exist_ok=True)
    r = t0.render(**tmpl_params['vm-cloud-init/user-data'])
    with open(out_fname0, mode='w') as f: f.write(r)
    tmpl_params['vm-cloud-init/meta-data'] = {}
    r = t1.render(**(tmpl_params['vm-cloud-init/meta-data']))
    with open(out_fname1, mode='w') as f: f.write(r)
  return {
    'actions': [gen_cloud_init_conf]
  , 'verbosity':2
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
  vmimage = outdir / 'de10pro-playground-user-vm.qcow2'
  usr_dsk = outdir / 'de10playground-user-disk.qcow2'
  def gen_vm_image():
    shutil.copy(f'{outdir}/de10pro-playground-vm.qcow2', vmimage)
    require_cmd('qemu-img')
    subprocess.run(['qemu-img', 'resize', vmimage, '16G'])
    subprocess.run([ 'qemu-system-x86_64', '-enable-kvm', '-m', '2048'
                   , '-machine', 'q35'
                   , '-drive', f'file={vmimage},if=virtio'
                   , '-drive', f'driver=raw,file={outdir}/vm-cloud-init/config.iso,if=virtio'
                   , '-drive', f'file={usr_dsk},if=virtio'
                   , '-nographic' ])
  return {
    'actions': [gen_vm_image]
  , 'file_dep': [ f'{outdir}/de10pro-playground-vm.qcow2'
                , f'{outdir}/vm-cloud-init/config.iso'
                ]
  , 'targets': [ vmimage ]
  }

def task_setup_playground():
  return {
    'actions': [f'echo "de10 playground setup in {outdir}"']
  , 'verbosity': 2
  , 'file_dep': [ outdir / fname for fname in ['de10playground-user-disk.qcow2'] ]
  }
