import os
import yaml
import logging
from . import pkgs as pkgs

logger = logging.getLogger(__name__)

class Installer:
	def install(self, instance_id=None, desc={}):
		pass

	def update(self, instance_id=None, desc={}):
		pass

	def uninstall(self, instance_id=None, desc={}):
		pass

def load_pkgs():
	pkg_descriptions = {}

	pkg_dir = os.path.dirname(pkgs.__file__)
	
	for fn in os.listdir(pkg_dir):
		abs_path = os.path.join(pkg_dir, fn)
		fn_lower = fn.lower()
		if os.path.isfile(abs_path) and (fn_lower.endswith('.yml') or fn_lower.endswith('.yaml')):
			with open(abs_path, 'r', encoding='utf-8') as f:
				desc = yaml.load(f.read(), Loader=yaml.FullLoader)
				if 'id' in desc:
					pkg_descriptions[desc['id']] = desc

	return pkg_descriptions