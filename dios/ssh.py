import sys
import logging
from pssh.clients import ParallelSSHClient

#https://github.com/ParallelSSH/parallel-ssh/blob/master/pssh/utils.py
host_logger = logging.getLogger('pssh.host_logger')
host_logger.setLevel(logging.CRITICAL)

logger = logging.getLogger('ssh_logger')

class OutputIterator:
	def __init__(self, it):
		self.__it = it

	def __next__(self):
		return next(self.__it)

	def __iter__(self):
		return self

class Response:
	def __init__(self, host, exit_code, stdout, stderr, exception):
		self.host = host
		self.exit_code = exit_code
		self.stdout = stdout
		self.stderr = stderr
		self.exception = exception

class Connection:
	def __init__(self, hosts, user=None, password=None):
		self.hosts = hosts
		self.user = user
		self.password = password

		self.ssh_client = ParallelSSHClient(hosts, user, password)

	def run(self, cmd, consume_output=False):
		output = self.ssh_client.run_command(cmd, stop_on_errors=False)
		
		#When output from commands is not needed, it is best to use client.join(consume_output=True) so that output buffers are consumed automatically.
		#If output is not read or automatically consumed by join output buffers will continually grow, resulting in increasing memory consumption while the client is running, though memory use rises very slowly.
		self.ssh_client.join(consume_output=consume_output)

		for host_out in output:
			yield Response(host_out.host,
				host_out.exit_code, 
				OutputIterator(host_out.stdout), 
				OutputIterator(host_out.stderr), 
				host_out.exception)

def is_success(ri):
	if type(ri) == Response:
		return not (ri.exit_code == None or ri.exit_code != 0)

	success = True
	for r in ri:
		if r.exit_code == None or r.exit_code != 0:
			success = False
			break
	return success

def print_response(r, stdout=True):
	color = '\x1b[32m'
	reset = '\x1b[0m'
	if r.exit_code == None or r.exit_code != 0:
		color = '\x1b[31m'

	if r.exit_code == None:
		logger.error("%s%s%s" % (color, r.exception, reset))
	else:
		logger.info('%s[%s] [%s]%s' % (color, r.host, 'OK' if r.exit_code == 0 else 'FAILED', reset))
		if stdout:
			print('STDOUT:\n', file=sys.stdout)
			for l in r.stdout:
				print(l, file=sys.stdout)
			print('\n', file=sys.stdout)

		if r.exit_code != 0:
			print('STDERR:\n', file=sys.stderr)
			for l in r.stderr:
				print(l, file=sys.stderr)
			print('\n', file=sys.stderr)

def print_responses(ri, stdout=True):
	for r in ri:
		print_response(r)

def get_stdout(r):
	r = list(r)
	success = is_success(r)
	if success:
		return '\n'.join(list(r[0].stdout))
	else:
		print_responses(r)


class TryrunConnection:
	def __init__(self, hosts, user=None, password=None):
		self.hosts = hosts
		self.user = user
		self.password = password

	def run(self, cmd, consume_output=False):
		logger.info("Tryrun: %s " % cmd)
		for host in self.hosts:
			yield Response(0, OutputIterator(iter([])), OutputIterator(iter([])), None)