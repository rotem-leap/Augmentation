import re
import numpy as np
from augmentor.modules import Tree, TRIM_MAX_REPEAT, InnerNode
from augmentor.keywords import KeywordFactory


class RegexSampler:

    def __init__(self):
        self.tree = Tree()
        self.max_repeat_stack = []
        self.in_weight_reading = False
        self.weights_list = []
        self.branch_stack = []
        self.branch_weights_stack = []
        self.branch_current_weights = []
        self.branch_active_id = -1

        self.all_chars = [chr(x) for x in range(32, 127)]
        self.digits = [chr(x) for x in range(48, 58)]
        self.not_digits = list(set(self.all_chars).difference(set(self.digits)))

        self.small = [chr(x) for x in range(97, 123)]
        self.capital = [chr(x) for x in range(65, 91)]

        self.letters = self.small.copy()
        self.letters.extend(self.capital)
        self.not_letters = list(set(self.all_chars).difference(set(self.letters)))

        self.alnum = self.digits.copy()
        self.alnum.extend(self.letters)  # this is called word
        self.not_alnum = list(set(self.all_chars).difference(set(self.alnum)))

        self.wspace = [' ', '\t', '\n', '\r', '\f', '\v']
        self.not_wspace = list(set(self.all_chars).difference(set(self.wspace)))

        self.all_chars_with_wspace = self.all_chars.copy() + self.wspace.copy()

        self.OPEN_IN_WEIGHT = 60
        self.CLOSE_IN_WEIGHT = 62
        self.DUMMY_ID = -1
        self.char_counter = 0
        self.last_open_in_position = -1
        self.keep_father_for_regret = -1
        self.keep_brother_for_regret = -1

        self.OPEN_BRANCH_WEIGHT = 126
        self.unsupported_keywords = {
            #           'MIN_REPEAT',
            'ASSERT',
        }

        self.keywords = {
            'AT',
            'MAX_REPEAT',
            'SUBPATTERN',
            'BRANCH',
            'IN',
            'GROUPREF'
        }

        self.generalized_literals_keyword = {
            'LITERAL',
            'NOT_LITERAL',
            'CATEGORY',
            'RANGE',
            'ANY',
        }

        self.in_params = {  # no need for that just for the sake of completeness
            'NEGATE'
        }

        self.at_params = {
            'AT_BEGINNING': ['@@^@@ '],
            'AT_END': [' @@$@@'],
            'AT_BOUNDARY': [' @@b@@ '],
            'AT_NON_BOUNDARY': ['@@B@@ '],
        }

        self.category_params = {
            'CATEGORY_DIGIT': self.digits,
            'CATEGORY_NOT_DIGIT': self.not_digits,
            'CATEGORY_WORD': self.alnum,
            'CATEGORY_NOT_WORD': self.not_alnum,
            'CATEGORY_SPACE': self.wspace,
            'CATEGORY_NOT_SPACE': self.not_wspace,
        }

        self.weights_boundary = '<>'

        self.repeat_params = {'MAXREPEAT': TRIM_MAX_REPEAT}
        self.keywords_factory = KeywordFactory(self)

    def calibrate(self):
        self.max_repeat_stack = []
        self.in_weight_reading = False
        self.weights_list = []
        self.branch_stack = []
        self.branch_weights_stack = []
        self.branch_current_weights = []
        self.branch_active_id = -1
        self.char_counter = 0
        self.last_open_in_position = -1
        self.keep_father_for_regret = -1
        self.keep_brother_for_regret = -1

    def get_sample_from_traverse(self, max_samples, do_print):
        sample = set()
        i = 0
        max_iterations = int(np.floor(5 * max_samples * (np.log(max_samples) + 1)))
        sample_with_freq = dict()

        while (len(sample) < max_samples) and (i < max_iterations):
            i += 1
            lst = self.tree.traverse_tree(do_print, seed=None)
            x = ''.join(lst)
            if x in sample:
                sample_with_freq[x] += 1
            else:
                sample.add(x)
                sample_with_freq[x] = 1

        return list(sample), sample_with_freq

    def generate_tree(self, regex, max_samples=100, print_tree=False):
        self.calibrate()
        self.generate(re.sre_parse.parse(regex).data)
        if print_tree:
            self.tree.print()

        return self.get_sample_from_traverse(max_samples, print_tree)

    def generate(self, regex, start_of_expression=True, father_id=-1, brother_id=-1):
        if start_of_expression:
            start_of_expression = False
            node = InnerNode()
            node.type_str = 'EXPRESSION'
            node_id = self.tree.add_inner_node(node, father_id, brother_id)
            self.generate(regex, start_of_expression, node_id, -1)
            return node_id

        if not start_of_expression:
            if len(regex) == 0:
                return -1

            current = regex[0]
            rest_of_expression = regex[1:]
            assert (type(current) == tuple)
            assert (len(current) > 0)

            node_id = self.keywords_factory.get_keyword(current).handle(current, father_id, brother_id)
            self.generate(rest_of_expression, start_of_expression, -1, node_id)
            return node_id
