import numpy as np

TRIM_MAX_REPEAT = 5


class Leaf:

    def __init__(self):
        self.options = []

    def add_option(self, option):
        self.options.append(str(option))

    def num_options(self):
        return len(self.options)

    def print(self, leaf_id):
        n = self.num_options()
        if n > TRIM_MAX_REPEAT:
            n = TRIM_MAX_REPEAT
        print('@@@leaf id: ', leaf_id, ' options: ', self.options[:n])


class InnerNode:

    def __init__(self):
        self.child_id = -1
        self.brother_id = -1
        self.leaf_id = -1
        self.type_str = ''
        self.type_specific_info = []
        self.traverse_info = {}

    def print(self, inner_node_id=None):
        if inner_node_id is None:
            print('@@@node son:', self.child_id, ' brother: ', self.brother_id, ' leaf: ', self.leaf_id, ' ',
                  self.type_str, ' auxiliary: ', self.type_specific_info)
        else:
            print('@@@node: ', inner_node_id, ' son:', self.child_id, ' brother: ', self.brother_id, ' leaf: ',
                  self.leaf_id, ' ', self.type_str, ' auxiliary: ', self.type_specific_info)
        pass


class Tree:
    def __init__(self):
        self.inner_nodes = []
        self.leaves = []
        self.group_to_node_id = {}
        self.traverse_output = []
        self.node_ids_in_traverse = []

    def add_leaf(self, leaf):
        self.leaves.append(leaf)
        return len(self.leaves) - 1

    def add_inner_node(self, node, parent_id, brother_id):
        self.inner_nodes.append(node)
        inner_node_id = len(self.inner_nodes) - 1
        self.update_father(inner_node_id, parent_id)
        self.update_brother(inner_node_id, brother_id)
        return inner_node_id

    def update_father(self, child_id, father_id):
        if father_id != -1:
            self.inner_nodes[father_id].child_id = child_id

    def update_brother(self, node_id, brother_id):
        if brother_id != -1:
            self.inner_nodes[brother_id].brother_id = node_id

    def clear_traverse_info(self):
        for seg in self.inner_nodes:
            seg.traverse_info = {}

    def print(self):
        print('@@@tree nSeg: ', len(self.inner_nodes), ' nLeaves: ', len(self.leaves),
              ' nGroups: ', len(self.group_to_node_id))
        for i in range(len(self.leaves)):
            self.leaves[i].print(i)
        for i in range(len(self.inner_nodes)):
            self.inner_nodes[i].print(i)

    def traverse_tree(self, do_print=False, seed=1108):
        if len(self.inner_nodes) == 0:
            return []
        if seed is not None:
            np.random.seed(seed)
        self.node_ids_in_traverse = []
        self.traverse_output = []
        self.clear_traverse_info()
        self.traverse(node_id=0, do_print=do_print)
        return self.traverse_output

    def traverse(self, node_id, do_print):
        assert (node_id is not None)  # this means something was not updated
        curr = self.inner_nodes[node_id]

        if do_print:
            curr.print()
        if curr.leaf_id != -1:
            options = self.leaves[curr.leaf_id].options
            n = len(options)
            if n == 0:
                raise Exception(f'Invalid leaf {curr.leaf_id} node: {node_id}')
            if n == 1:
                x = options[0]
            else:
                x = options[np.random.randint(0, n, 1)[0]]
            self.traverse_output.extend(x)
        else:
            if curr.type_str == 'GROUPREF':
                group_id = curr.type_specific_info[0]
                node_id = self.group_to_node_id[group_id]
                str_to_copy = self.inner_nodes[node_id].traverse_info['str_value']
                self.traverse_output.extend(str_to_copy)

            elif curr.type_str == 'GROUP':  # this is subpatteren
                start_of_str = len(self.traverse_output)
                self.traverse(curr.child_id, do_print)
                curr.traverse_info['str_value'] = self.traverse_output[start_of_str:]
            elif curr.type_str == 'MAX_REPEAT':
                if len(curr.type_specific_info[0]) == 0:
                    options_weights_lst = [1 for i in
                                           list(range(curr.type_specific_info[1], curr.type_specific_info[2]))]
                else:
                    options_weights_lst = curr.type_specific_info[0]
                helper_id = random_according_to_weights(options_weights_lst)
                num_repeats = curr.type_specific_info[1] + helper_id  # you draw an offset
                if do_print:
                    do_print('@@@ num_repeats: ', num_repeats, ' weights: ', curr.type_specific_info[2])
                for i in range(num_repeats):
                    self.traverse(curr.child_id, do_print)
            elif curr.type_str == 'BRANCH':
                # curr.type_specific_info[0] contains the drawing weight for each option
                n = len(curr.type_specific_info) - 1
                if n == 1:
                    child_id = curr.type_specific_info[1]
                else:
                    helper_id = random_according_to_weights(curr.type_specific_info[0])
                    child_id = curr.type_specific_info[1 + helper_id]
                    if do_print:
                        do_print('@@@ branch_id: ', child_id, ' weights: ', curr.type_specific_info[0])
                self.traverse(child_id, do_print)
            else:
                if curr.type_str != 'EXPRESSION':
                    raise Exception(f'Wrong type {node_id}')
                else:
                    self.traverse(curr.child_id, do_print)

        if curr.brother_id != -1:
            self.traverse(curr.brother_id, do_print)
        return


def random_according_to_weights(weights):
    x = np.cumsum(np.array(weights, dtype=int))
    max_index = len(weights) - 1
    high = x[max_index]
    rand_int = np.random.randint(0, high)
    for i in range(len(weights)):
        if rand_int < x[i]:
            return i
