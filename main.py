import os
import time
from io import StringIO

from typing import Optional, Dict, List

import sh
import yaml
import click

import pandas as pd

import seaborn as sns
import matplotlib.pyplot as plt

from tqdm import tqdm


def load_config(fname: str) -> Dict:
    with open(fname) as fd:
        return yaml.load(fd)


class Repository:
    def __init__(self, url: str, config: str) -> None:
        self.url = url

        self.config_dir = os.path.dirname(config)
        self.config = load_config(config)
        os.makedirs(self.config['working_directory'])

    def clone(self) -> None:
        sh.git.clone(self.url, 'repo', _cwd=self.config['working_directory'])

    def clean(self) -> None:
        wd = os.path.join(self.config['working_directory'], 'repo')
        sh.git.checkout('.', _cwd=wd)

    def switch_to_commit(self, commit_id: str) -> None:
        wd = os.path.join(self.config['working_directory'], 'repo')

        # switch to commit
        sh.git.checkout(commit_id, _cwd=wd)

        # prepare environment
        cmd_path = os.path.join(self.config_dir, self.config['init_script'])
        os.system(f'cd "{wd}" && {cmd_path} > /dev/null')

    def execute(self) -> List:
        wd = os.path.join(self.config['working_directory'], 'repo')

        stats = []
        for job in tqdm(self.config['jobs'], desc='Jobs'):
            cmd_path = os.path.join(self.config_dir, job['command'])
            # cmd = sh.Command(cmd_path)

            start = time.time()
            # cmd(_cwd=wd)
            os.system(f'cd "{wd}" && {cmd_path} > /dev/null')
            dur = time.time() - start

            stats.append((job['name'], dur))
        return stats

    def handle_commit(self, commit_id: str) -> List:
        self.clean()
        self.switch_to_commit(commit_id)
        return self.execute()

    def list_commits(self) -> List[str]:
        wd = os.path.join(self.config['working_directory'], 'repo')

        buf = StringIO()
        sh.git(
            'rev-list', '--all', _out=buf,
            _cwd=wd)
        return buf.getvalue().split()

    def run(self, commits: Optional[List[str]] = None) -> List:
        self.clone()

        stats = []
        commits = commits or self.list_commits()

        for commit in tqdm(commits, desc='Commit history'):
            res = self.handle_commit(commit)
            stats.append((commit, res))
        return stats

    def plot(self, data: List) -> None:
        # transform data
        tmp = []
        for commit, jobs in data:
            for name, duration in jobs:
                tmp.append((commit[:5], name, duration))
        df = pd.DataFrame(tmp, columns=['commit', 'job', 'time'])

        # plot
        sns.pointplot(x='commit', y='time', hue='job', data=df)

        plt.xticks(rotation=90)
        plt.xlabel('Commits [id]')
        plt.ylabel('Execution time [s]')
        plt.title('Performance overview')

        plt.tight_layout()
        plt.savefig(os.path.join(
            self.config['working_directory'], 'performance.pdf'))


@click.command()
@click.argument('repo_url')
@click.option(
    '--config', required=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help='Path to config.')
@click.option(
    '-c', '--commit', multiple=True,
    help='Commit id to consider.')
def main(repo_url: str, config: str, commit: List[str]) -> None:
    """ Performance and and stability profiling over the git commit history.
    """
    repo = Repository(repo_url, config)

    res = repo.run(commit)
    repo.plot(res)


if __name__ == '__main__':
    main()
