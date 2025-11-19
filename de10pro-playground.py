#! /usr/bin/env python3

import sys
import argparse
import subprocess
from pathlib import Path

if __name__ == "__main__":
  # command line arguments
  parser = argparse.ArgumentParser(description='setup de10pro playground files')
  subparsers = parser.add_subparsers(help='sub-command help', dest='cmd')

  parser_setup = subparsers.add_parser('setup', help='setup the de10 playground files')
  parser_setup.add_argument(
    '--template-parameters', metavar='YAML_TEMPLATE_PARAMETERS', default='template-parameters.yaml'
  , help="The YAML_TEMPLATE_PARAMETERS yaml file with the jinja template parameters to use")
  parser_setup.add_argument(
    '--template-directory', metavar='TEMPLATE_DIRECTORY'
  , type = Path, default = Path('./templates')
  , help="The TEMPLATE_DIRECTORY containing the jinja templates")
  parser_setup.add_argument(
    '-d', '--output-directory', metavar='OUT_DIR'
  , type = Path, default = Path('./setup_output')
  , help='The OUT_PATH path to the output directory' )

  parser_run = subparsers.add_parser('run', help='run the de10 playground')
  parser_run.add_argument('run_directory', metavar='RUN_DIR'
  , default=[Path('./setup_output')]
  , nargs='+'
  , help='The RUN_DIR path(s) to the folder(s) with a vm image and optionally a payload image to run. If more than one path is specified, a tmux session is created with a window per run.' )

  # parse command line arguments
  #clargs=parser.parse_args()
  clargs, rest = parser.parse_known_args()

  if not clargs.cmd:
    sys.stderr.write('\n')
    sys.stderr.write('/!\\ No command was specified /!\\\n')
    sys.stderr.write('\n')
    parser.print_help()
    sys.exit(2)

  if clargs.cmd == 'setup':
    from doit.cmd_base import ModuleTaskLoader
    from doit.doit_cmd import DoitMain
    import de10pro_playground_setup_doit_tasks
    de10pro_playground_setup_doit_tasks.init_ctxt(
      template_parameters=clargs.template_parameters
    , template_directory=clargs.template_directory.absolute()
    , output_directory=clargs.output_directory.absolute()
    )
    sys.exit(DoitMain(ModuleTaskLoader(de10pro_playground_setup_doit_tasks)).run(rest))

  if clargs.cmd == 'run':
    def spawn_playground_cmd(d, board_id=None):
      if not (d / 'de10pro-playground-user-vm.qcow2').exists():
        sys.stderr.write(f'no de10pro-playground-user-vm.qcow2 found in {d}\n')
        sys.exit(1)
      cmd = [ '/opt/de10playground/bin/de10playground' ]
      if board_id != None:
        cmd.append(f'-s{board_id}')
        cmd.append(f'-e{board_id}')
      if (d / 'de10playground-user-disk.qcow2').exists():
        cmd.extend(['-u', (d / 'de10playground-user-disk.qcow2').absolute()])
      cmd.append((d / 'de10pro-playground-user-vm.qcow2').absolute())
      return cmd
    nruns = len(clargs.run_directory)
    if nruns == 1:
      subprocess.run(spawn_playground_cmd(Path(clargs.run_directory[0])))
    elif nruns > 1:
      import libtmux
      srv = libtmux.Server()
      sess = srv.new_session('de10pro-playground')
      for _ in range(1, nruns): sess.new_window()
      for i, d in enumerate(clargs.run_directory):
        p = sess.windows[i].panes[0]
        p.send_keys(' '.join(spawn_playground_cmd(Path(d), board_id=i)))
