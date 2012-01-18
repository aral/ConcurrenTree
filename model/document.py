from ConcurrenTree.model import ModelBase
from ConcurrenTree.model.node import make
from ConcurrenTree.model.operation import Operation, FromNode

class Document(ModelBase):
	''' Stores a node and tracks operations. '''

	def __init__(self, root, applied = []):
		self.root = make(root)

		self.applied = set(applied)

	def apply(self, op, track=True):
		''' Apply an operation and track its application '''
		op.apply(self.root)
		if track:
			self.applied.add(op.hash)

	def load(self, json):
		self.apply(Operation(json[0]), False)
		self.applied = set(json[1])

	def flatten(self):
		return self.root.flatten()

	def proto(self):
		''' Fully serializes document. Not a terribly fast function. '''
		return [FromNode(self.root, 0).proto(), self.applylist]

	@property
	def applylist(self):
		result = list(self.applied)
		result.sort()
		return result
