import json
import traceback

from ConcurrenTree.model import operation, address
from ConcurrenTree.util.server.pool.connection import Connection
from peer import Peer
from errors import errors

nullbyte = "\x00"

class BCPConnection(Connection):
	''' A connection between two Peers '''
	def __init__(self, docs, auth):
		Connection.__init__(self)
		self.docs = docs
		self.auth = auth

		self.here = Peer()
		self.there = Peer()

	def incoming(self, value):
		if nullbyte in value:
			length = value.index(nullbyte)
			try:
				self.recv(value[:length])
			finally:
				return value[length+1:]
		else:
			return value

	def recv(self, msg):
		''' Takes a textual BCP message of unknown validity '''
		print "recving message:",msg
		try:
			obj = json.loads(msg)
		except ValueError:
			self.error(451) # Bad JSON
			return
		if type(obj)!=dict:
			self.error(454) # Wrong root type
			return
		try:
			self.analyze(obj, msg)
		except:
			traceback.print_exc()
			self.error(500)

	def outgoing(self, msg):
		return json.dumps(msg)+nullbyte

	def push(self, msgtype, **kwargs):
		kwargs['type'] = msgtype
		self.send(kwargs)

	def send(self, msg):
		print "sending message:",msg
		self.ioqueue.client_push(json.dumps(msg)+nullbyte)

	def select(self, docname):
		if self.here.selected != docname:
			self.push("select", docname=docname)

	def analyze(self, obj, objstring):
		''' 
			Apply a message as a piece of remote communication.
		'''
		obt = obj['type']
		if obt=='select':
			if not self.require("docname", obj): return
			self.there.selected = obj['docname']
		elif obt=='op':
			if not self.check_selected():return
			if not self.require("instructions", obj): return
			try:
				op = operation.Operation(instructions = obj['instructions'])
			except operation.ParseError:
				return self.error(453)
			# TODO: authorize
			try:
				op.apply(self.fdoc)
			except operation.OpApplyError:
				self.error(500) # General Local Error
		elif obt=='ad':
			if not self.require("hash", obj): return
			elif not obj['hash'] in self.here.ops:
				self.select(self.there.selected)
				self.push("getop", hash=obj['hash'])
		elif obt=='getop':
			if not self.check_selected():
				return
			if not self.require("hash", obj): return
			try:
				op = self.fdoc.operations[obj['hash']]
				self.push(str(op))
			except KeyError:
				self.error(502, data={
					"type":"operation",
					"docname":self.there.selected,
					"operation":obj['hash']
				}) # Resource not found
		elif obt=='check':
			# TODO - error testing
			if not self.check_selected():return
			if not self.require("address", obj):return
			addr = address.Address(obj['address'])
			sum = addr.resolve(self.fdoc).treesum
			self.select(self.there.selected)
			self.push("tsum",address=addr.proto(), value=sum)
		elif obt=='tsum':
			if not self.check_selected():return
			if not self.require("address", obj):return
			if not self.require("value", obj):return
			# Compare to our own treesum
			addr = address.Address(obj['address'])
			sum = addr.resolve(self.fdoc).treesum
			if sum != obj['value']:
				self.push("get", address=addr.proto(), depth=1)
		elif obt=='get':
			if not self.check_selected():return
			if not self.require("address", obj):return
			if not self.require("value", obj):return
			addr = address.Address(obj['address'])
			node = addr.resolve(self.fdoc)
			if "depth" in obj:
				result = node.proto(obj['depth'])
			else:
				result = node.proto()
			self.push("tree", address = addr.proto(), value=result)
		elif obt=='tree':
			if not self.check_selected():return
			if not self.require("address", obj):return
			if not self.require("value", obj):return
			addr = address.Address(obj['address'])
			node = addr.resolve(self.fdoc)
			node.upgrade(obj['value'])
		elif obt=='subscribe':
			if "subtype" not in obj or obj['subtype']=="live":
				# live subscription
				for name in obj['docnames']:
					self.there.subscriptions[name] = ("live",)
			elif obj['subtype']=="notify":
				# notify subscription (ad-only)
				for name in obj['docnames']:
					self.there.subscriptions[name] = ("notify",)
			elif obj['subtype']=="marked":
				# notify subscription (read/unread)
				for name in obj['docnames']:
					self.there.subscriptions[name] = ("marked", 0) # TODO use tree hash

		elif obt=='unsubscribe':
			if "docnames" in obj and len(obj['docnames']) > 0:
				for name in obj['docnames']:
					del self.there.subscriptions[name]
			else:
				self.there.subscriptions.clear()
		elif obt=='error':
			print obj
		else:
			self.error(401) # Unknown Message Type

	def check_selected(self, is_loaded=True):
		if not self.there.selected:
			return self.error(405) # No document selected
		if is_loaded and not self.there.selected in self.docs:
			return self.error(404) # Document not found
		return True

	def require(self, arg, obj):
		if not arg in obj:
			self.error(452, 'Missing required argument: "%s"' % arg, arg)
			return False
		return True

	def error(self, num=500, details="", data=None):
		if num in errors and not details:
			details = errors[num]
		if data != None:
			self.push("error", code=num, details=details, data=data)
		else:
			self.push("error", code=num, details=details)

	@property
	def fdoc(self):
		''' Foreign selected document '''
		return self.docs[self.there.selected]

	@property
	def ldoc(self):
		''' Locally selected document '''
		return self.docs[self.here.selected]
