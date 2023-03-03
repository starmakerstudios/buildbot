import base64
import os
import urllib
import json

from twisted.python.log import ILogObserver, FileLogObserver
from twisted.python.logfile import LogFile
from twisted.application import service
from buildbot_worker.bot import Worker

BUILDBOT_MASTER = os.getenv('BUILDBOT_MASTER')
BUILDBOT_URL = os.getenv('BUILDBOT_URL')
BUILDBOT_USER = os.getenv('BUILDBOT_USER')
BUILDBOT_PASSWORD = os.getenv('BUILDBOT_PASSWORD')
BUILDBOT_WORKER_CPUS = os.getenv('BUILDBOT_WORKER_CPUS', '3')
BUILDBOT_SSH_KEY = os.getenv('BUILDBOT_SSH_KEY')
GITHUB_USER = os.getenv('GITHUB_USER', 'hero')
CODESPACE_NAME = os.getenv('CODESPACE_NAME', 'Nameless')
HOSTNAME = os.getenv('HOSTNAME', 'Borderlands')

environBlacklists = (
    'BUILDBOT_',
    'CODESPACE',
    'GITHUB_',
    'INTERNAL_',
    'CLOUDENV_',
    'VSCODE_'
)
for name in list(os.environ.keys()):
    for prefix in environBlacklists:
        if name.startswith(prefix):
            os.unsetenv(name)
            del os.environ[name]

if BUILDBOT_SSH_KEY:
    try:
        os.mkdir('/home/code/.ssh')
    except FileExistsError:
        pass

    sshConfig = open('/home/code/.ssh/config', 'w')
    sshConfig.write('StrictHostKeyChecking no\n')
    sshConfig.close()
    os.chmod('/home/code/.ssh/config', 0o600)

    sshKey = open('/home/code/.ssh/id_rsa', 'w')
    sshKey.write(base64.b64decode(BUILDBOT_SSH_KEY).decode())
    sshKey.close()
    os.chmod('/home/code/.ssh/id_rsa', 0o600)


WORKERS_URL = BUILDBOT_URL + '/api/v2/workers'

passwordManager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
passwordManager.add_password(
    None, WORKERS_URL, BUILDBOT_USER, BUILDBOT_PASSWORD
)
urllib.request.install_opener(
    urllib.request.build_opener(
        urllib.request.HTTPBasicAuthHandler(passwordManager)
    )
)
response = urllib.request.urlopen(WORKERS_URL)
workers = json.loads(response.read().decode())

workerName = ''

for worker in workers['workers']:
    if len(worker['connected_to']) == 0:
        workerName = worker['name']
        break

if not workerName:
    print('no available worker, abort')
    exit(1)

print('worker name: ' + workerName)


baseDir = '/home/code/buildbot'
rotateLength = 10000000
maxRotatedFiles = 10

infoDir = baseDir + '/info'
try:
    os.mkdir(infoDir)
except FileExistsError:
    pass
adminFile = open(infoDir + '/admin', 'w')
adminFile.write('%s <%s@%s>' % (GITHUB_USER, GITHUB_USER, HOSTNAME))
adminFile.close()

hostFile = open(infoDir + '/host', 'w')
hostFile.write(CODESPACE_NAME)
hostFile.close()

application = service.Application('buildbot-worker')

logFile = LogFile.fromFullPath(
    os.path.join(baseDir, "twistd.log"), rotateLength=rotateLength,
    maxRotatedFiles=maxRotatedFiles
)
application.setComponent(ILogObserver, FileLogObserver(logFile).emit)


buildMasterHost = BUILDBOT_MASTER.split(':')[0]
port = int(BUILDBOT_MASTER.split(':')[1])
passwd = BUILDBOT_PASSWORD
keepalive = 600
umask = None
maxDelay = 300
numCpus = int(BUILDBOT_WORKER_CPUS)
allowShutdown = None
maxRetries = None
useTls = 0
deleteLeftoverDirs = 0

s = Worker(
    buildMasterHost, port, workerName, passwd, baseDir, keepalive, umask=umask,
    maxdelay=maxDelay, numcpus=numCpus, allow_shutdown=allowShutdown,
    maxRetries=maxRetries, useTls=useTls,
    delete_leftover_dirs=deleteLeftoverDirs
)
s.setServiceParent(application)
