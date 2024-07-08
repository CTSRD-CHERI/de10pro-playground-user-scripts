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

from doit.task import dict_to_task
from doit.cmd_base import TaskLoader2
from doit.doit_cmd import DoitMain


# Doit tasks #
################################################################################

task_dicts = []

class AllTasks(TaskLoader2):

  def __init__(self, clargs):
    tmpl_env = jinja2.Environment(loader=jinja2.FileSystemLoader(clargs.template_directory))
    tmpl_params = {k: {} for k in tmpl_env.list_templates()}
    if hasattr(clargs, 'template_parameters') \
      and clargs.template_parameters is not None:
      with open(clargs.template_parameters, mode='r') as f:
        tmpl_params = yaml.safe_load(f)
    self.outdir = clargs.output_path
    self.tmpl_env = tmpl_env
    self.tmpl_params = tmpl_params

  def setup(self, _):
    pass

  def load_doit_config(self):
    return {'verbosity': 2}

  def __get_freebsd_aarch64_rootfs(self):
    def get_freebsd_aarch64_rootfs():
      os.makedirs(self.outdir, exist_ok=True)
      subprocess.run([ 'rsync'
                     , 'caravel.cl.cam.ac.uk:/auto/anfs/bigdisc/aj443/freebsd-aarch64-rootfs.tar'
                     , f'{self.outdir}/freebsd-aarch64-rootfs.raw.tar' ])
    return {
      'name': 'get-freebsd-aarch64-rootfs'
    , 'actions': [get_freebsd_aarch64_rootfs]
    , 'targets': [f'{self.outdir}/freebsd-aarch64-rootfs.raw.tar']
    , 'uptodate': [True]
    }

  def __gen_ssh_keys(self):
    def gen_keys():
      with tempfile.TemporaryFile("w+") as f:
        f.write('y')
        subprocess.run([ 'ssh-keygen', '-N', '""', '-f', f'{self.outdir}/key' ], stdin=f)
    return {
      'name': 'gen-ssh-keys'
    , 'actions': [gen_keys]
    , 'targets': [f'{self.outdir}/key', f'{self.outdir}/key.pub']
    , 'uptodate': [True]
    }

  def __install_aarch64_rootfs_ssh_keys(self):
    d = self.outdir
    def install_keys():
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
      'name': 'install-aarch64-rootfs-ssh-keys'
    , 'actions': [install_keys]
    , 'file_dep': [f'{d}/key', f'{d}/key.pub', f'{d}/freebsd-aarch64-rootfs.raw.tar']
    , 'targets': [f'{d}/freebsd-aarch64-rootfs.tar']
    }

  def __get_aarch64_bsd_loader(self):
    url = 'https://www.cl.cam.ac.uk/~jdw57/loader.efi'
    loader = f'{self.outdir}/payload/tftp/loader.efi'
    def get_loader():
      os.makedirs(f'{self.outdir}/payload/tftp/', exist_ok=True)
      urllib.request.urlretrieve(url, filename=loader)
    return {
      'name': 'get-aarch64-bsd-loader'
    , 'actions': [get_loader]
    , 'targets': [loader]
    , 'uptodate': [True]
    }

  def __get_bitfiles(self):
    d = f'{self.outdir}/payload/tftp'
    hps_rbf = f'{d}/fpga.hps.rbf'
    core_rbf = f'{d}/fpga.core.rbf'
    path = "caravel.cl.cam.ac.uk:/auto/anfs/bigdisc/aj443/"
    def get_bitfiles():
      os.makedirs(d, exist_ok=True)
      subprocess.run(['rsync', f'{path}/fpga.hps.rbf', hps_rbf])
      subprocess.run(['rsync', f'{path}/fpga.core.rbf', core_rbf])
    return {
      'name': 'get-bitfiles'
    , 'actions': [get_bitfiles]
    , 'targets': [hps_rbf, core_rbf]
    , 'uptodate': [True]
    }

  def __gen_uboot_stage2(self):
    t = self.tmpl_env.get_template('tftp/u-boot-stage2.cmd')
    out_fname = f'{self.outdir}/payload/tftp/u-boot-stage2.scr'
    def gen_uboot_stage2():
      r = t.render(**(self.tmpl_params['tftp/u-boot-stage2.cmd']))
      os.makedirs(f'{self.outdir}/payload/tftp', exist_ok=True)
      with tempfile.NamedTemporaryFile('w') as f:
        f.write(r)
        f.flush()
        require_cmd('mkimage')
        subprocess.run(['mkimage', '-T', 'script', '-d', f.name, out_fname])
    return {
      'name': 'gen-u-boot-stage2'
    , 'actions': [gen_uboot_stage2]
    , 'file_dep': [t.filename]
    , 'targets': [out_fname]
    }

  def __get_socfpga_stratix10_dtb(self):
    url = 'https://www.cl.cam.ac.uk/~aj443/socfpga_stratix10_de10_pro.dts.dtb'
    dtb = f'{self.outdir}/payload/tftp/socfpga_stratix10_de10_pro.dts.dtb'
    def get_dtb():
      os.makedirs(f'{self.outdir}/payload/tftp', exist_ok=True)
      urllib.request.urlretrieve(url, filename=dtb)
    return {
      'name': 'get-socfpga-stratix10-dtb'
    , 'actions': [get_dtb]
    , 'targets': [dtb]
    , 'uptodate': [True]
    }

  def __gen_nfs_conf(self):
    t = self.tmpl_env.get_template('conf/ganesha.conf')
    out_fname = f'{self.outdir}/payload/conf/ganesha.conf'
    def gen_nfs_conf():
      r = t.render(**(self.tmpl_params['conf/ganesha.conf']))
      os.makedirs(f'{self.outdir}/payload/conf', exist_ok=True)
      with open(out_fname, mode='w') as f:
        f.write(r)
    return {
      'name': 'gen-nfs-conf'
    , 'actions': [gen_nfs_conf]
    , 'file_dep': [t.filename]
    , 'targets': [out_fname]
    }

  def __gen_tftp_conf(self):
    t = self.tmpl_env.get_template('conf/tftpd-hpa')
    out_fname = f'{self.outdir}/payload/conf/tftpd-hpa'
    def gen_tftp_conf():
      r = t.render(**(self.tmpl_params['conf/tftpd-hpa']))
      os.makedirs(f'{self.outdir}/payload/conf', exist_ok=True)
      with open(out_fname, mode='w') as f:
        f.write(r)
    return {
      'name': 'gen-tftp-conf'
    , 'actions': [gen_tftp_conf]
    , 'file_dep': [t.filename]
    , 'targets': [out_fname]
    }

  def __gen_payload_runme(self):
    t = self.tmpl_env.get_template('runme.sh')
    out_fname = f'{self.outdir}/payload/runme.sh'
    def gen_runme():
      r = t.render(**(self.tmpl_params['runme.sh']))
      os.makedirs(f'{self.outdir}/payload', exist_ok=True)
      with open(out_fname, mode='w') as f:
        f.write(r)
      os.chmod(out_fname, 0o544)
    return {
      'name': 'gen-payload-runme'
    , 'actions': [gen_runme]
    , 'file_dep': [t.filename]
    , 'targets': [out_fname]
    }

  def __create_payload(self):
    d = f'{self.outdir}'
    pd = f'{d}/payload'
    fdeps = [
      f'{pd}/runme.sh'
    , f'{pd}/conf/tftpd-hpa'
    , f'{pd}/conf/ganesha.conf'
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
      'name': 'create-payload'
    , 'actions': [create_payload]
    , 'file_dep': fdeps
    , 'targets': [f'{d}/de10playground_payload.img']
    }

  def __get_ubuntu_cloud_image(self):
    vm_img = f'{self.outdir}/de10pro-playground-vm.qcow2'
    ubuntu_img_url="https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
    def get_img():
      tmp, _ = urllib.request.urlretrieve(ubuntu_img_url)
      shutil.move(tmp, vm_img)
    return {
      'name': 'get-ubuntu-cloud-image'
    , 'actions': [get_img]
    , 'targets': [vm_img]
    , 'uptodate': [True]
    }

  def __gen_cloud_init_conf(self):
    t0 = self.tmpl_env.get_template('vm-cloud-init/user-data')
    t1 = self.tmpl_env.get_template('vm-cloud-init/user-data')
    d = f'{self.outdir}/vm-cloud-init'
    out_fname0 = f'{d}/user-data'
    out_fname1 = f'{d}/meta-data'
    def gen_cloud_init_conf():
      sshkey = {'name': 'key'}
      with open(f'{self.outdir}/key','r') as key: sshkey['priv'] = key.read()
      with open(f'{self.outdir}/key.pub','r') as pkey: sshkey['pub'] = pkey.read()
      self.tmpl_params['vm-cloud-init/user-data'] = {'sshkeys': [sshkey]}
      os.makedirs(d, exist_ok=True)
      r = t0.render(**(self.tmpl_params['vm-cloud-init/user-data']))
      with open(out_fname0, mode='w') as f: f.write(r)
      self.tmpl_params['vm-cloud-init/meta-data'] = {}
      r = t1.render(**(self.tmpl_params['vm-cloud-init/meta-data']))
      with open(out_fname1, mode='w') as f: f.write(r)
    return {
      'name': 'gen-cloud-init-conf'
    , 'actions': [gen_cloud_init_conf]
    , 'file_dep': [t0.filename, t1.filename]
    , 'targets': [out_fname0, out_fname1]
    }

  def __gen_cloud_init_iso(self):
    userdata = f'{self.outdir}/vm-cloud-init/user-data'
    metadata = f'{self.outdir}/vm-cloud-init/meta-data'
    isoname = f'{self.outdir}/vm-cloud-init/config.iso'
    def gen_cloud_init_iso():
      with open(isoname, 'w') as _:
        require_cmd('mkisofs')
        subprocess.run([ 'mkisofs', '--output', isoname
                       , '-volid', 'cidata', '-joliet', '-rock'
                       , userdata, metadata ])
    return {
      'name': 'gen-cloud-init-iso'
    , 'actions': [gen_cloud_init_iso]
    , 'file_dep': [ f'{self.outdir}/vm-cloud-init/user-data'
                  , f'{self.outdir}/vm-cloud-init/meta-data'
                  ]
    , 'targets': [isoname]
    }

  def __gen_vm_image(self):
    vmimage = f'{self.outdir}/de10pro-playground-user-vm.qcow2'
    def gen_vm_image():
      shutil.copy(f'{self.outdir}/de10pro-playground-vm.qcow2', vmimage)
      require_cmd('qemu-img')
      subprocess.run(['qemu-img', 'resize', vmimage, '16G'])
      subprocess.run([ 'qemu-system-x86_64', '-enable-kvm', '-m', '2048'
                     , '-machine', 'q35'
                     , '-drive', f'file={vmimage},if=virtio'
                     , '-drive', f'driver=raw,file={self.outdir}/vm-cloud-init/config.iso,if=virtio'
                     , '-nographic' ])
    return {
      'name': 'gen-vm-image'
    , 'actions': [gen_vm_image]
    , 'file_dep': [ f'{self.outdir}/de10pro-playground-vm.qcow2'
                  , f'{self.outdir}/vm-cloud-init/config.iso'
                  ]
    , 'targets': [vmimage]
    }

  def __run_vm(self):
    def run_vm():
      subprocess.run([ '/opt/de10playground/bin/de10playground'
                     , f'{self.outdir}/de10pro-playground-user-vm.qcow2'
                     , f'{self.outdir}/de10playground_payload.img' ])
    return {
      'name': 'run-vm'
    , 'actions': [run_vm]
    , 'file_dep': [ f'{self.outdir}/de10pro-playground-user-vm.qcow2'
                  , f'{self.outdir}/de10playground_payload.img' ]
    }

  def load_tasks(self, cmd, pos_args):
    return map(dict_to_task, [ self.__get_freebsd_aarch64_rootfs()
                             , self.__gen_ssh_keys()
                             , self.__install_aarch64_rootfs_ssh_keys()
                             , self.__get_aarch64_bsd_loader()
                             , self.__get_bitfiles()
                             , self.__gen_uboot_stage2()
                             , self.__get_socfpga_stratix10_dtb()
                             , self.__gen_nfs_conf()
                             , self.__gen_tftp_conf()
                             , self.__gen_payload_runme()
                             , self.__create_payload()
                             , self.__get_ubuntu_cloud_image()
                             , self.__gen_cloud_init_conf()
                             , self.__gen_cloud_init_iso()
                             , self.__gen_vm_image()
                             , self.__run_vm()
                             ])

#x = DoitMain(AllTasks()).run(sys.argv[1:])
################################################################################


def require_cmd(cmd):
  if shutil.which(cmd) is None:
    print(f'\n/!\\ "{cmd}" is not available /!\\\n', file=sys.stderr)
    exit(1)

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

if __name__ == '__main__':

  # command line arguments
  parser = argparse.ArgumentParser(description='setup de10pro playground files')
  subparsers = parser.add_subparsers(
    dest='subcmd'
  , help='sub-command (run with -h on a specific sub-command for further help)' )

  # general, common options
  parser.add_argument(
    '--template-parameters', metavar='YAML_TEMPLATE_PARAMETERS', default='template-parameters.yaml'
  , help="The YAML_TEMPLATE_PARAMETERS yaml file with the jinja template parameters to use")
  parser.add_argument(
    '--template-directory', metavar='TEMPLATE_DIRECTORY', default='./templates'
  , help="The TEMPLATE_DIRECTORY containing the jinja templates")
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

  # parse command line arguments
  #clargs=parser.parse_args()
  clargs, rest = parser.parse_known_args()
  DoitMain(AllTasks(clargs)).run(rest)

#x = DoitMain(AllTasks()).run(sys.argv[1:])
  ## prepare templates and parameters
  #tmpl_env = jinja2.Environment(loader=jinja2.FileSystemLoader('templates/'))
  #tmpl_params = {k: {} for k in tmpl_env.list_templates()}
  #if hasattr(clargs, 'template_parameters') \
  #   and clargs.template_parameters is not None:
  #  with open(clargs.template_parameters, mode='r') as f:
  #    tmpl_params = yaml.safe_load(f)

  ## ensure output folders exists
  #os.makedirs(clargs.output_path, exist_ok=True)
  #for p in map(pathlib.Path, tmpl_params.keys()):
  #  os.makedirs(f'{clargs.output_path}/{p.parent}', exist_ok=True)

  ## there must be a sub-command
  #if not hasattr(clargs, 'subcmd') or clargs.subcmd is None:
  #  print('\n/!\\ No sub-command was passed /!\\\n', file=sys.stderr)
  #  parser.print_help(sys.stderr)
  #  sys.exit(1)

  #main_process(tmpl_env, tmpl_params, clargs)
