import logging
from .. import Installer
import dios.ssh

logger = logging.getLogger('dios')

class DockerCEInstaller(Installer):

	install_scripts = """

sudo apt-get install -y conntrack

sudo apt-get remove -y docker docker-engine docker.io containerd runc

sudo apt-get update
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update

sudo apt-get install -y docker-ce docker-ce-cli containerd.io

sudo mkdir /etc/docker
cat <<EOF | sudo tee /etc/docker/daemon.json
{
  "exec-opts": ["native.cgroupdriver=systemd"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m"
  },
  "storage-driver": "overlay2"
}
EOF

sudo usermod -a -G docker `whoami`

docker run hello-world

	"""
	
	def install(self, instance_id=None, desc={}):
		success = False
		result = {}

		hosts = [] if 'hosts' not in desc else desc['hosts']
		params = {} if 'params' not in desc else desc['params']

		# pre check
		if len(hosts) == 0:
			result['error'] = 'hosts is empty'
			return (success, result)

		ssh = dios.ssh.Connection(hosts, params.get('user'), params.get('password'))

		scripts = self.install_scripts

		success = True

		for rs in ssh.run(scripts):
			suc = dios.ssh.is_success(rs)

			if not suc:
				success = False
				dios.ssh.print_response(rs)
			else:
				stdout = '\n'.join(list(rs.stdout))
				if stdout.find('Hello from Docker!') == -1:
					success = False
					result['error'] = 'hello world docker dontainer is not running'
					print(stdout)

		return (success, result)

