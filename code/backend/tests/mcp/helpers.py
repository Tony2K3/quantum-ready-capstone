"""Small lookups shared by the test files."""


def by_name(nodes, name):
    return next(n for n in nodes if n.name == name)


def edge_between(edges, nodes, from_name, to_name):
    a, b = by_name(nodes, from_name), by_name(nodes, to_name)
    return [e for e in edges if e.from_node_id == a.id and e.to_node_id == b.id]


async def instant_sleep(_seconds):
    return None
