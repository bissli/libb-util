import logging
import os
import sys
import time

import docker
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.append('..')
import config

logger = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def ftp_docker(request):
    client = docker.from_env()
    container = client.containers.run(
        image='garethflowers/ftp-server',
        auto_remove=True,
        environment={
            'FTP_USER': config.vendor.FOO.ftp.username,
            'FTP_PASS': config.vendor.FOO.ftp.password,
            },
        name='ftp_server',
        ports={
            f'{port}/tcp': (config.vendor.FOO.ftp.hostname, f'{port}/tcp')
            for port in [20, 21]+list(range(40000,40010))
            },
        volumes={config.tmpdir.dir: {'bind': '/data', 'mode': 'rw'}},
        detach=True,
        remove=True,
    )
    time.sleep(5)
    request.addfinalizer(container.stop)
