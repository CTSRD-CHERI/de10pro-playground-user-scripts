#! /usr/bin/env python3

import os
import sys
import argparse
import subprocess

if __name__ == "__main__":
  # command line arguments
  parser = argparse.ArgumentParser(description='setup de10pro playground files')
  subparsers = parser.add_subparsers(help='sub-command help', dest='cmd')

  cwd = os.getcwd()

  parser_setup = subparsers.add_parser('setup', help='setup the de10 playground files')
  parser_setup.add_argument(
    '--template-parameters', metavar='YAML_TEMPLATE_PARAMETERS', default='template-parameters.yaml'
  , help="The YAML_TEMPLATE_PARAMETERS yaml file with the jinja template parameters to use")
  parser_setup.add_argument(
    '--template-directory', metavar='TEMPLATE_DIRECTORY', default=f'{cwd}/templates'
  , help="The TEMPLATE_DIRECTORY containing the jinja templates")
  parser_setup.add_argument(
    '-d', '--output-directory', metavar='OUT_DIR', default=f'{cwd}/setup_output'
  , help='The OUT_PATH path to the output directory' )

  parser_run = subparsers.add_parser('run', help='run the de10 playground')
  parser_run.add_argument('run_directory', metavar='RUN_DIR'
  , default=['./setup_output']
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
    , template_directory=clargs.template_directory
    , output_directory=clargs.output_directory
    )
    sys.exit(DoitMain(ModuleTaskLoader(de10pro_playground_setup_doit_tasks)).run(rest))

  if clargs.cmd == 'run':
    def spawn_playground_cmd(d, board_id=None):
      if not os.path.isfile(f'{d}/de10pro-playground-user-vm.qcow2'):
        sys.stderr.write(f'no de10pro-playground-user-vm.qcow2 found in {d}\n')
        sys.exit(1)
      cmd = [ '/opt/de10playground/bin/de10playground' ]
      if board_id != None:
        cmd.append(f'-s{board_id}')
        cmd.append(f'-e{board_id}')
      cmd.append(f'{d}/de10pro-playground-user-vm.qcow2')
      if os.path.isfile(f'{d}/de10playground_payload.img'):
        cmd.append(f'{d}/de10playground_payload.img')
      return cmd
    nruns = len(clargs.run_directory)
    if nruns == 1:
      subprocess.run(spawn_playground_cmd(clargs.run_directory[0]))
    elif nruns > 1:
      import libtmux
      srv = libtmux.Server()
      sess = srv.new_session('de10pro-playground')
      for _ in range(1, nruns): sess.new_window()
      for i, d in enumerate(clargs.run_directory):
        p = sess.windows[i].panes[0]
        p.send_keys(' '.join(spawn_playground_cmd(d, board_id=i)))
