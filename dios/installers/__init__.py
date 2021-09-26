from .. import Installer

installers = {}

def register(id, installer):
	global installers

	installers[id] = installer

def create_installer(id):
	global installers

	return None if id not in installers else installers[id]()

from .docker_ce_installer import DockerCEInstaller
register('docker-ce', DockerCEInstaller)

from .kubernetes_installer import KubernetesInstaller
register('kubernetes', KubernetesInstaller)