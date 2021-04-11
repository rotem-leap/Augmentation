import numpy as np
import pandas as pd
import re

from augmentor.Regex import RegexSampler
from augmentor.reader import ExpressionsReader


class Augmentor:
    def __init__(self, expressions_fname, utterances_fname, read_utterances_as_text=True):  # type: ignore
        self.expr_reader = ExpressionsReader()
        self.expressions_df = self.expr_reader.read_expressions(expressions_fname)
        self.output_only_expr = self.expressions_df[self.expressions_df.output_only == True].copy()
        self.expressions_df = self.expressions_df[self.expressions_df.output_only == False].copy()
        self.utterances = self.read_utterances_file(utterances_fname, read_utterances_as_text)
        self.rules_counter = 0
        self.current_utter_fragmentations = []

    def read_utterances_file(self, utterances_fname, as_text=True):
        if type(utterances_fname) == list:
            all = []
            for f in utterances_fname:
                all.extend(self.read_utterances_file(f))
            return all

        if as_text:
            file_handler = open(utterances_fname, "r")
            utterances = file_handler.readlines()
            file_handler.close()
        else:
            converters = {"response": self.normalize_utterance}
            df = pd.read_csv(utterances_fname, comment="#", converters=converters)
            utterances = df["response"].values.tolist()
            utterances = utterances[:10]
        return utterances

    def calc_variations(self, max_variants=500, do_print=False):
        out = {}
        for utterance in self.utterances:
            variations = self.get_variations_list(utterance, max_variants)
            print("Uniqe variations:")
            print(len(list(set(variations))))
            print(list(set(variations)))
            out[utterance] = [self.normalize_variation(v) for v in variations]

        if do_print:
            print('@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@')
            for msg, val in out.items():
                print(f'\nText: {msg}')
                for v in val:
                    print(v)

        return out

    def get_variations_list(self, utter, max_variants=100):
        print(f"Original = {utter}")
        utter = self.change_to_logical_rules(utter)
        print(f"Convert To Logical Rules = {utter}")
        print()
        self.current_utter_fragmentations = self.get_utter_fragmentations(utter, max_variants)
        return self.calc_variations_for_utterance(max_variants)

    def change_to_logical_rules(self, utter):
        new_utter = utter
        utter += ' '

        # look for in-text regex definition
        for match in re.finditer('\([a-zA-Z0-9 |%~<>+?*:,]+\)', utter):
            match_str = utter[match.start(): match.end()]
            logical_rule = re.findall('[a-zA-Z0-9_]+:', match_str)
            if logical_rule:
                logical_rule = logical_rule[0][:-1]
                replace_to = f'<<{logical_rule}>>'
                exp = '(' + utter[utter.index(':') + 1: match.end()]
            else:
                x = self.expressions_df[self.expressions_df['expression'] == f'({match_str})']
                if len(x) > 0:
                    replace_to = str(x['logical_rule_name'].to_list()[0])
                else:
                    replace_to = f'<<{self.rules_counter}>>'
                exp = match_str

            df = pd.DataFrame([[exp, replace_to]], columns=["expression", "logical_rule_name"])
            df = self.expr_reader.replace_output_only(df)
            self.expressions_df = self.expressions_df.append(df)
            new_utter = new_utter.replace(match_str, replace_to)

        # look for match according to regex
        for i in range(len(self.expressions_df)):
            exp = str(self.expressions_df.iloc[i].expression)[:-1] + '+[^>>])'
            exp = self.clean_exp(exp)
            for exp_match in re.finditer(exp, new_utter):
                to_replace = new_utter[exp_match.start(): exp_match.end() - 1]
                replace_by = self.expressions_df.iloc[i].logical_rule_name
                new_utter = new_utter.replace(to_replace, replace_by)

        return new_utter

    def clean_exp(self, exp):
        new_exp = exp
        for match in re.finditer('( ~[0-9]*|<[0-9]+(,[0-9]+)*>)', exp):
            to_replace = exp[match.start(): match.end()]
            start = new_exp.index(to_replace)
            new_exp = new_exp[:start] + new_exp[start + len(to_replace):]

        return new_exp

    def get_utter_fragmentations(self, utter, max_variants):
        frags = []
        last_frag = 0
        for match in re.finditer('<<[a-zA-Z0-9_]+>>', utter):
            frags.append([utter[last_frag: match.start()]])
            last_frag = match.end()
            logical_rule = utter[match.start(): match.end()]
            curr_exp = \
                self.expressions_df[self.expressions_df['logical_rule_name'] == logical_rule].expression.to_list()[0]

            reg_samp = RegexSampler()

            _, options_freq = reg_samp.generate_tree(curr_exp, max_variants)
            frag = []
            for key in options_freq.keys():
                if 'QQQ' not in key:
                    frag.extend(int(options_freq[key]) * [key])
            frags.append(frag)

        frags.append([utter[last_frag:]])
        return frags

    def calc_variations_for_utterance(self, max_variants):
        variation = []
        for _ in range(max_variants):
            variant = []
            for frag in self.current_utter_fragmentations:
                if len(frag) == 1:
                    variant.extend(frag)
                else:
                    to_add = frag[np.random.randint(0, len(frag), 1)[0]]
                    variant.append(to_add)
            v = "".join(variant)
            variation.append(v)
        return variation

    def normalize_variation(self, v):
        v = re.sub("@@\w+@@", " ", v)  # Remove @@x@@ notations
        v = re.sub("\s{2,}", " ", v)  # double+ whitespace
        v = v.strip()
        return v

    def normalize_utterance(self, s):
        s = s.lower()
        s = s.strip()
        return s

    def no_logical_rules(self, utter):
        match = [re.findall('<<[A-Za-z0-9_]+>>', u) for u in utter]
        return len(np.array(match).flatten()) == 0

    def get_list(self, row_index, logical_rule, utters):
        if type(utters) != list:
            utters = [utters]
        alternatives = []
        for utter in utters:
            for _ in re.finditer(logical_rule, utter):
                exp = self.expressions_df.iloc[row_index].expression
                for exp_match in re.finditer('[^<<]([ A-Za-z0-9_]+)', exp):
                    e = exp[exp_match.start() + 1: exp_match.end()]
                    if 'QQQ' not in e:
                        x = utter.replace(logical_rule, e)
                        alternatives.append(x)

        return alternatives
