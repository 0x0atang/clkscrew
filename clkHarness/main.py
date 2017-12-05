import click
import numpy as np

# local
import utils
import config
from enginelib import Engine
from enginelib import TaskPdelayProfiling, TaskGlitchProfiling, TaskGlitchRsa, \
    TaskGlitchExpt

TASKS = [TaskPdelayProfiling, TaskGlitchProfiling, TaskGlitchRsa, TaskGlitchExpt]



@click.command()
@click.option('--task', default='', help="task (pdelayprof, glitchprof, rsaauth, glitchexpt)")
@click.argument('device', required=True)
def main(device, task):
    
    # Parse DEVICE
    if not device in config.DEV_TYPES:
        click.echo('ERROR: Given device (%s) is invalid!' % device)
        return
    for c in config.CONFIGS:
        if config.DEV_TYPES[device] == c.DEVICE_TYPE:
            click.echo('DEVICE TYPE: %s' % config.DEV_TYPES[c.DEVICE_TYPE])
            cfg_ = c
    
    # Parse TASK
    if not task:
        click.echo('TASK: Rebooting only\n')
    if task:
        if not task in config.TASK_TYPES:
            click.echo('ERROR: Given task (%s) is invalid!' % task)
            return
        for t in TASKS:
            if config.TASK_TYPES[task] == t.TASK:
                click.echo('TASK: %s\n' % config.TASK_TYPES[t.TASK])
                task_ = t
    
    # main engine to perform the heavy lifting
    engine = Engine(cfg_)
    engine.reboot()
    if not task:
        return
    
    # Perform task
    task_(engine).run()



# =============================================================================
if __name__ == '__main__':
    
    # init folders
    utils.ensure_dir(config.DIR_LOG)
    utils.ensure_dir(config.DIR_SESSION)
    
    main()
