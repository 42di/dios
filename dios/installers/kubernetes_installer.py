import logging
from .. import Installer
from dios.ssh import Connection
from dios.ssh import print_responses
from dios.ssh import is_success
from dios.ssh import get_stdout

logger = logging.getLogger('dios')

def connect(hosts, params):
	return Connection(hosts, params.get('user'), params.get('password'))

class KubernetesInstaller(Installer):

	def install_kubeadm(self, hosts, params):
		ssh = connect(hosts, params)

		scripts = """

# iptables
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
br_netfilter
EOF

cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-ip6tables = 1
net.bridge.bridge-nf-call-iptables = 1
EOF
sudo sysctl --system

CNI_VERSION="v0.8.2"
ARCH="amd64"
sudo mkdir -p /opt/cni/bin
curl -L "https://github.com/containernetworking/plugins/releases/download/${CNI_VERSION}/cni-plugins-linux-${ARCH}-${CNI_VERSION}.tgz" | sudo tar -C /opt/cni/bin -xz

DOWNLOAD_DIR=/usr/local/bin
sudo mkdir -p $DOWNLOAD_DIR

CRICTL_VERSION="v1.17.0"
ARCH="amd64"
curl -L "https://github.com/kubernetes-sigs/cri-tools/releases/download/${CRICTL_VERSION}/crictl-${CRICTL_VERSION}-linux-${ARCH}.tar.gz" | sudo tar -C $DOWNLOAD_DIR -xz

RELEASE="$(curl -sSL https://dl.k8s.io/release/stable.txt)"
ARCH="amd64"
cd $DOWNLOAD_DIR
sudo curl -L --remote-name-all https://storage.googleapis.com/kubernetes-release/release/${RELEASE}/bin/linux/${ARCH}/{kubeadm,kubelet,kubectl}
sudo chmod +x {kubeadm,kubelet,kubectl}

RELEASE_VERSION="v0.4.0"
curl -sSL "https://raw.githubusercontent.com/kubernetes/release/${RELEASE_VERSION}/cmd/kubepkg/templates/latest/deb/kubelet/lib/systemd/system/kubelet.service" | sed "s:/usr/bin:${DOWNLOAD_DIR}:g" | sudo tee /etc/systemd/system/kubelet.service
sudo mkdir -p /etc/systemd/system/kubelet.service.d
curl -sSL "https://raw.githubusercontent.com/kubernetes/release/${RELEASE_VERSION}/cmd/kubepkg/templates/latest/deb/kubeadm/10-kubeadm.conf" | sed "s:/usr/bin:${DOWNLOAD_DIR}:g" | sudo tee /etc/systemd/system/kubelet.service.d/10-kubeadm.conf

sudo systemctl enable --now kubelet

	"""
		rs = list(ssh.run(scripts))

		if not is_success(rs):
			print_responses(rs)
			return False, 'install kubeadm failed'

		return True, None

	def get_token(self, cp, params):
		ssh =connect([cp], params)

		token = get_stdout(ssh.run("kubeadm token create")).strip()

		ca_hash = get_stdout(ssh.run("""
openssl x509 -pubkey -in /etc/kubernetes/pki/ca.crt | openssl rsa -pubin -outform der 2>/dev/null | \
	openssl dgst -sha256 -hex | sed 's/^.* //'
			""")).strip()

		return token, ca_hash

	def get_cer_key(self, cp, params):
		ssh = connect([cp], params)
		cer_key = get_stdout(ssh.run("sudo kubeadm init phase upload-certs --upload-certs|tail -1")).strip()
		return cer_key

	def deploy_control_plane(self, hosts, params):
		if len(hosts) == 0: return False

		cp0 = hosts[0]

		ssh = connect([cp0], params)

		scripts = """

rm -rf ~/.kube

sudo kubeadm init --control-plane-endpoint=%s \
	--pod-network-cidr=10.244.0.0/16 \
	--apiserver-advertise-address=0.0.0.0 \
	--upload-certs \
	--image-repository registry.aliyuncs.com/google_containers

mkdir -p ~/.kube
sudo cp /etc/kubernetes/admin.conf ~/.kube/config
sudo chown admin:admin ~/.kube/config

kubectl apply -f https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel.yml
	""" % (cp0)

		rs = list(ssh.run(scripts))

		success = is_success(rs)

		if not success:
			dios.ssh.print_responses(rs)
			return False, 'initialize control-plane failed'

		return True, None

	def add_control_plane(self, cp0, hosts, params):
		token, ca_hash = self.get_token(cp0, params)
		cer_key = self.get_cer_key(cp0, params)

		scripts = """
sudo kubeadm join %s:6443 --token %s \
	--discovery-token-ca-cert-hash sha256:%s \
	--control-plane \
	--certificate-key %s
		""" % (cp0, token, ca_hash, cer_key)
		
		if len(hosts) > 1:
			ssh = connect(hosts, params)
			rs = list(ssh.run(scripts))

			success = is_success(rs)
			if not success:
				print_responses(rs)
				return False, 'add control plane failed'

		return True, None


	def add_worker_nodes(self, cp, hosts, params):
		token, ca_hash = self.get_token(cp, params)

		ssh = connect(hosts, params)

		scripts = """sudo kubeadm join %s:6443 --token %s --discovery-token-ca-cert-hash sha256:%s""" % (cp, token, ca_hash)

		rs = list(ssh.run(scripts))

		success = is_success(rs)
		if not success:
			print_responses(rs)
			return False, 'add worker nodes failed'

		return True, None

	def install(self, instance_id=None, desc={}):
		success = True
		error = None
		result = {}

		params = desc.get('params', {})
		control_plane_nodes = params.get('control_plane_nodes',[])
		worker_nodes = params.get('worker_nodes', [])

		all_nodes = control_plane_nodes + worker_nodes

		success, error = self.install_kubeadm(all_nodes, params)

		if success:
			success, error = self.deploy_control_plane(control_plane_nodes, params)

		if success:
			success, error = self.add_control_plane(control_plane_nodes[0], control_plane_nodes[1:], params)

		if success:
			success, error = self.add_worker_nodes(control_plane_nodes[0], worker_nodes, params)

		result['error'] = error
		return success, result