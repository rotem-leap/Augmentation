from augmentor import Augmentor

expr_fname = './regex_table.csv'
utter_fname = './texts.txt'

u = Augmentor(expr_fname, utter_fname)
vr = u.calc_variations(100, do_print=True)

