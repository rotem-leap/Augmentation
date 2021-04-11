from augmentor.modules import Leaf, InnerNode


class Keyword:
    def __init__(self, regex_sampler, key_type):
        self.type = key_type
        self.regex_sampler = regex_sampler

    def handle(self, current, father_id, brother_id, t='IN'):
        pass


class MaxRepeatKeyword(Keyword):
    def __init__(self, regex_sampler):
        Keyword.__init__(self, regex_sampler, 'MAX_REPEAT')

    def handle(self, current, father_id, brother_id, t='IN'):
        params = current[1]

        min_repeat = params[0]
        max_repeat = params[1]
        if str(max_repeat) == 'MAXREPEAT':
            max_repeat = max(self.regex_sampler.repeat_params['MAXREPEAT'], min_repeat + 1)

        node = InnerNode()
        node.type_str = 'MAX_REPEAT'
        node.type_specific_info = [[], min_repeat, max_repeat + 1]
        id = self.regex_sampler.tree.add_inner_node(node, father_id, brother_id)
        self.regex_sampler.max_repeat_stack.append(id)
        self.regex_sampler.generate(params[2], start_of_expression=True, father_id=id, brother_id=-1)

        return id


class GroupRefKeyword(Keyword):
    def __init__(self, regex_sampler):
        Keyword.__init__(self, regex_sampler, 'GROUPREF')

    def handle(self, current, father_id, brother_id, t='IN'):
        group_id = current[1]
        if str(group_id) not in self.regex_sampler.tree.group_to_node_id.keys():
            raise Exception(f'Non-existing group: {group_id}')

        node = InnerNode()
        node.type_str = 'GROUPREF'
        node.type_specific_info.append(str(group_id))

        return self.regex_sampler.tree.add_inner_node(node, father_id, brother_id)


class BranchKeyword(Keyword):
    def __init__(self, regex_sampler):
        Keyword.__init__(self, regex_sampler, 'BRANCH')

    def handle(self, current, father_id, brother_id, t='IN'):
        branch_list = current[1][1]
        n = len(branch_list)
        node = InnerNode()
        node.type_str = 'BRANCH'
        node.type_specific_info.append([])  # the first item would be the weights
        node_id = self.regex_sampler.tree.add_inner_node(node, father_id, brother_id)
        self.regex_sampler.branch_stack.append(node_id)
        self.regex_sampler.branch_weights_stack.append([])
        for i in range(n):
            ## note that for this command we have multiple sons and they are
            ## kept in the list, so we don't update the son field of this node
            ## by moving -1 as the father_id

            alternative_id = self.regex_sampler.generate(branch_list[i], start_of_expression=True, father_id=-1,
                                                         brother_id=-1)
            node.type_specific_info.append(alternative_id)
            if len(self.regex_sampler.branch_current_weights) > 0:
                branch_weight = int(''.join(self.regex_sampler.branch_current_weights))
                self.regex_sampler.branch_current_weights = []
            else:
                branch_weight = 1
            self.regex_sampler.branch_weights_stack[-1].append(branch_weight)
            self.regex_sampler.branch_active_id = -1

        node.type_specific_info[0] = self.regex_sampler.branch_weights_stack.pop(
            len(self.regex_sampler.branch_weights_stack) - 1)
        self.regex_sampler.branch_active_id = -1
        return self.regex_sampler.branch_stack.pop(len(self.regex_sampler.branch_stack) - 1)


class LiteralKeyword(Keyword):
    def __init__(self, regex_sampler):
        Keyword.__init__(self, regex_sampler, 'LITERAL')
        self.in_keyword = InKeyword(regex_sampler)

    def handle(self, current, father_id, brother_id, t='IN'):
        return self.in_keyword.handle([current], father_id, brother_id, 'LITERAL')


class InKeyword(Keyword):
    def __init__(self, regex_sampler):
        Keyword.__init__(self, regex_sampler, 'IN')

    def handle(self, current, father_id, brother_id, t='IN'):
        literals_list = current
        if t == 'IN':
            literals_list = current[1]
        if len(literals_list) == 0:
            raise Exception(f'Error in IN literals list {literals_list}')

        if t != 'SKIP':
            result = self.handle_non_skip(literals_list, father_id, brother_id)
            if result is not None:
                return result

        negate_result = False
        if str(literals_list[0][0]) == 'NEGATE':
            negate_result = True
            literals_list = literals_list[1:]

        literals_list_chr = []
        for lit in literals_list:
            literals_list_chr.extend(self.get_literals(str(lit[0]), lit[1]))
        literals_list_chr = list(set(literals_list_chr))

        if negate_result:
            literals_list_chr = list(set(self.regex_sampler.all_chars_with_wspace).difference(set(literals_list_chr)))

        leaf = Leaf()
        for literal in literals_list_chr:
            leaf.add_option(literal)
        pos = self.regex_sampler.tree.add_leaf(leaf)
        node = InnerNode()
        if t == 'SKIP':
            node.type_str = 'LITERAL'
        else:
            node.type_str = t
        node.leaf_id = pos
        node_id = self.regex_sampler.tree.add_inner_node(node, father_id, brother_id)
        return node_id

    def get_literals(self, literal_type, param):
        if literal_type == 'LITERAL':
            return [chr(param)]

        if literal_type == 'NOT_LITERAL':
            # always keep two options for not literal
            return list(self.regex_sampler.all_chars_with_wspace.difference(set(chr(param))))

        if literal_type == 'RANGE':
            return [chr(x) for x in range(param[0], param[1])]

        if literal_type == 'CATEGORY':
            return self.regex_sampler.category_params[str(param)].copy()

        if literal_type == 'ANY':
            pass
            # return self.regex_sampler._wrap_extensions(self.regex_sampler.all_chars_with_wspace)

        raise Exception(f'Error, unknown literal type: {literal_type},  param: {param}')

    def handle_non_skip(self, literals, father_id, brother_id):
        self.regex_sampler.char_counter += 1

        if literals[0][1] == self.regex_sampler.OPEN_IN_WEIGHT:
            if self.regex_sampler.char_counter != (self.regex_sampler.last_open_in_position + 1):
                # a special case, this may not be a literal but the open of weights list for the  previous max_repeat
                assert (self.regex_sampler.in_weight_reading is False)
                self.regex_sampler.in_weight_reading = True
                self.regex_sampler.weights_list = []
                self.regex_sampler.last_open_in_position = self.regex_sampler.char_counter
                self.regex_sampler.keep_father_for_regret = father_id
                self.regex_sampler.keep_brother_for_regret = brother_id
                return brother_id
            else:
                self.regex_sampler.in_weight_reading = False
                self.regex_sampler.weights_list = []
                prev_open_id = self.handle(literals, self.regex_sampler.keep_father_for_regret,
                                           self.regex_sampler.keep_brother_for_regret, 'SKIP')
                self.regex_sampler.keep_father_for_regret = -1
                self.regex_sampler.keep_brother_for_regret = -1
                return self.handle(literals, -1, prev_open_id, 'SKIP')

        if literals[0][1] == self.regex_sampler.CLOSE_IN_WEIGHT:
            # a special case, this may not be a literal but end of the weights list for the  previous max_repeat
            if self.regex_sampler.in_weight_reading:
                self.regex_sampler.in_weight_reading = False
                self.finalize_in_weight_list()
                return brother_id

        if self.regex_sampler.in_weight_reading:
            self.regex_sampler.weights_list = self.regex_sampler.weights_list + list(chr(literals[0][1]))
            return brother_id

        if (literals[0][1] == self.regex_sampler.OPEN_BRANCH_WEIGHT) and len(
                self.regex_sampler.branch_weights_stack) > 0:
            # support weights for branch
            self.regex_sampler.branch_current_weights = []
            self.regex_sampler.branch_active_id = self.regex_sampler.branch_stack[-1]
            return brother_id

        if self.regex_sampler.branch_active_id != -1:
            self.regex_sampler.branch_current_weights = self.regex_sampler.branch_current_weights + list(
                chr(int(literals[0][1])))
            return brother_id

    def finalize_in_weight_list(self):
        length = len(self.regex_sampler.max_repeat_stack)
        assert (length > 0)
        in_weight_values_str = ''.join(self.regex_sampler.weights_list).split(',')
        self.regex_sampler.keep_father_for_regret = -1
        self.regex_sampler.keep_brother_for_regret = -1

        n_weights = len(in_weight_values_str)
        in_weight_values = []
        for i in range(n_weights):
            if len(in_weight_values_str[i]) > 0:
                in_weight_values.append(int(in_weight_values_str[i]))

        n_weights = len(in_weight_values)

        id_to_update = self.regex_sampler.max_repeat_stack.pop(length - 1)
        min_times = self.regex_sampler.tree.inner_nodes[id_to_update].type_specific_info[1]
        max_times = self.regex_sampler.tree.inner_nodes[id_to_update].type_specific_info[
            2]  # if we allow 3,4,5 then this would be 6
        n_options = max_times - min_times
        if n_options < n_weights:
            in_weight_values = in_weight_values[:n_options]
        for k in range(n_weights, n_options):
            in_weight_values.append(1)
        self.regex_sampler.tree.inner_nodes[id_to_update].type_specific_info[0] = in_weight_values
        self.regex_sampler.last_max_repeat = self.regex_sampler.DUMMY_ID


class SubpatternKeyword(Keyword):
    def __init__(self, regex_sampler):
        Keyword.__init__(self, regex_sampler, 'SUBPATTERN')

    def handle(self, current, father_id, brother_id, t='IN'):
        param = current[1]
        node = InnerNode()
        node.type_str = 'GROUP'
        node.type_specific_info.append(str(param[0]))
        node_id = self.regex_sampler.tree.add_inner_node(node, father_id, brother_id)
        self.regex_sampler.tree.group_to_node_id[str(param[0])] = node_id
        self.regex_sampler.generate(param[3], start_of_expression=True, father_id=node_id, brother_id=-1)
        return node_id


class AtKeyword(Keyword):
    def __init__(self, regex_sampler):
        Keyword.__init__(self, regex_sampler, 'AT')

    def handle(self, current, father_id, brother_id, t='IN'):
        value = str(current[1])
        if value in self.regex_sampler.at_params:
            leaf = Leaf()
            leaf.add_option(self.regex_sampler.at_params[value][0])
            pos = self.regex_sampler.tree.add_leaf(leaf)
            node = InnerNode()
            node.type_str = 'AT'
            node.leaf_id = pos
            node_id = self.regex_sampler.tree.add_inner_node(node, father_id, brother_id)
        else:
            raise Exception(f'Error unsupprted at param for AT {value}')
        return node_id


class KeywordFactory:
    def __init__(self, regex_sampler):
        self.regex_sampler = regex_sampler

    def get_keyword(self, current_tuple):
        expression_type = str(current_tuple[0])
        if expression_type in self.regex_sampler.unsupported_keywords:
            raise Exception(f'Error {current_tuple[0]} is not supported {current_tuple}')
        elif expression_type == 'AT':
            return AtKeyword(self.regex_sampler)
        elif expression_type == 'MAX_REPEAT':
            return MaxRepeatKeyword(self.regex_sampler)
        elif expression_type == 'SUBPATTERN':
            return SubpatternKeyword(self.regex_sampler)
        elif expression_type == 'IN':
            return InKeyword(self.regex_sampler)
        elif expression_type in self.regex_sampler.generalized_literals_keyword:
            return LiteralKeyword(self.regex_sampler)
        elif expression_type == 'BRANCH':
            return BranchKeyword(self.regex_sampler)
        elif expression_type == 'GROUPREF':
            return GroupRefKeyword(self.regex_sampler)

        raise Exception(f'Error: unsupported command that was not caught {current_tuple}')
