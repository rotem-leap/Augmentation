import re
import pandas as pd


class ExpressionsReader:
    def __init__(self):  # type: ignore
        return

    # Normalizing regex
    def normalize_expr(self, exp):
        exp = exp.strip(" \t\r\n|")
        exp = exp.replace("||", "|")
        exp = re.sub("  +", " ", exp)
        return exp

    # Clean redundant parentheses
    # ...((expr))... => ...(expr)...
    # It may work otherwise, but not elegant
    def clean_redundant_parentheses(self, s):
        return re.sub(r"\((\([^()]+\))\)", r"\1", s)

    # Bound expression by parentheses if needed (not already bound)
    def bound_with_parentheses(self, s):
        with_par = "(" + s + ")"
        if s[0] != "(":
            return with_par
        cnt = 1
        for c in s[1:]:
            if cnt == 0:  # Closed before the end
                return with_par
            cnt += 1 if c == "(" else -1 if c == ")" else 0
        return s if (cnt == 0) else with_par

    def percents_locations(self, expr):
        locs = []
        last_begining_stack = []

        i = -1
        num_open_brackets = 0
        while i < len(expr) - 1:
            i += 1
            if expr[i] in '([':
                last_begining_stack.append(i)
                num_open_brackets += 1
                continue
            if expr[i] in ')]':
                last_begining_stack.pop(len(last_begining_stack) - 1)
                num_open_brackets -= 1
                continue
            if expr[i] == '|':
                if num_open_brackets > 0:
                    last_begining_stack[-1] = i
                else:
                    last_begining_stack.append(i)
                continue
            if expr[i] == '%':
                fr = last_begining_stack[-1]
                if i == len(expr) - 1:
                    locs.append((last_begining_stack[-1] + 1, i + 1))
                else:
                    if expr[i + 1] not in ')|]':
                        continue  # ignore the % sign since it is not output only
                    else:
                        locs.append((last_begining_stack[-1] + 1, i + 1))

        return locs

    def replace_output_only(self, df):
        exprs = df.expression.values
        dummy_name = 'QQQ'
        dummy_name_counter = 0
        new_expr_dict = {"expression": [], "logical_rule_name": []}
        for i in range(len(df)):
            expr = '(' + exprs[i] + ')'

            perc_locations_list = self.percents_locations(expr)
            fr = 0
            out_i = []
            for loc in perc_locations_list:
                to = loc[0]
                out_i.extend(expr[fr:to])
                dummy_expr = 'QQQ' + str(dummy_name_counter) + 'QQQ'
                dummy_name_counter += 1
                combined_expr = expr[loc[0]:(loc[1] - 1)]  # to-1 so as to remove the %
                new_expr_dict["expression"].append(combined_expr)
                new_expr_dict["logical_rule_name"].append(dummy_expr)
                out_i.extend(dummy_expr)
                fr = loc[1]
            to = len(expr)
            if to > fr:
                out_i.extend(expr[fr:to])
            out_i = "".join(out_i)
            exprs[i] = out_i

        df["output_only"] = 0
        if len(new_expr_dict) > 0:
            df_new = pd.DataFrame(new_expr_dict)
            df_new["output_only"] = 1
            df = pd.concat([df, df_new]).copy()
        return df

    # reads the expressions and remove back references in expressions
    def read_expressions(self, expressions_fname):

        cols = ["expression", "logical_rule_name"]
        converters = {'expression': self.normalize_expr, 'logical_rule_name': self.normalize_expr}  # Trimming
        if type(expressions_fname) == list:
            dfs = []
            for fn in expressions_fname:
                dfs.append(pd.read_csv(fn, comment="#", header=None, names=cols, converters=converters))
            df = pd.concat(dfs, axis=0, ignore_index=True)
        else:
            df = pd.read_csv(expressions_fname, comment="#", header=None, names=cols, converters=converters,
                             delimiter=';')
        df = self.replace_output_only(df)

        df["seen"] = 0

        df_output_only = df[df.output_only == True].copy()
        df = df[df.output_only == False].copy()

        # Since regular expressions may contain references to other expressions,
        # we do a topological sort of the expressions. In case there are cyclic
        # references you end up with an empty queue and raise an assert.
        # Note: we don't want to claculate these references on the output only rules.
        queue_ = []
        ref_regex = "(<<[A-Za-z0-9_]+>>)"
        for index, row_ in df.iterrows():
            has_subexpressions = False
            # sorry, the _ is linter's request
            for _ in re.finditer(ref_regex, row_.expression):
                has_subexpressions = True
            if not has_subexpressions:
                queue_.append(index)
                df.at[index, 'seen'] = 1
        head_of_q = 0
        while len(queue_) > head_of_q:
            curr = df.iloc[queue_[head_of_q]].logical_rule_name
            curr_exp = df.iloc[queue_[head_of_q]].expression
            for index, row_ in df.iterrows():
                # prevents infinite loop
                if df.iloc[index]['seen'] > 0:
                    continue
                str_parts = []
                from_pos = 0
                changed = False
                expr = row_.expression
                for match in re.finditer(curr, expr):
                    changed = True
                    start_pos = match.start()
                    end_pos = match.end()
                    str_parts.extend(expr[from_pos:start_pos])
                    str_parts.extend(self.bound_with_parentheses(curr_exp))
                    from_pos = end_pos
                str_parts.extend(expr[from_pos: len(expr)])
                if changed:
                    str_parts = self.clean_redundant_parentheses("".join(str_parts))
                    df.expression.values[index] = str_parts
                    # this is after the update
                    if len(re.findall(ref_regex, str_parts)) == 0:
                        queue_.append(index)
                        df.at[index, 'seen'] = 1
            head_of_q = head_of_q + 1

        # Fixing order of df according to queue_
        queue_.reverse()
        df = df.reindex(queue_).reset_index(drop=True)
        if min(df.seen.values) == 0:
            assert "Error "  # there is a cyclic reference so not everything is covered

        df = pd.concat([df, df_output_only]).copy()
        df.reset_index(drop=True, inplace=True)
        df.drop(columns="seen", inplace=True)
        return df
