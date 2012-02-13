from ConcurrenTree.model import node
import string, map

def make(node_obj):
	# Create a context object
	t = type(node_obj)
	if t == node.StringNode:
		return string.StringContext(node_obj)
	elif t == node.MapNode:
		return map.MapContext(node_obj)
