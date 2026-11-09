
# This file was generated automatically

# action 0 for: 
def action0(kids) :
	return kids

# action 1 for: [(0) Stmt -> RptStmt]
def action1(kids) :
	return kids[0]
	

# action 2 for: [(1) Stmt -> NoRptStmt]
def action2(kids) :
	return kids[0]
	

# action 3 for: [(2) RptStmt -> WATCH Stmt]
def action3(kids) :
	return ("watch", None, kids[1])
	

# action 4 for: [(3) RptStmt -> WATCH NUMBER NoRptStmt]
def action4(kids) :
	return ("watch", kids[1], kids[2])
	

# action 5 for: [(4) NoRptStmt -> QUIT]
def action5(kids) :
	return ("quit", )
	

# action 6 for: [(5) NoRptStmt -> LIST]
def action6(kids) :
	return ("list", )
	

# action 7 for: [(6) NoRptStmt -> INSPECT tsid]
def action7(kids) :
	return ("inspect", kids[1])
	

# action 8 for: [(7) NoRptStmt -> ROUTE]
def action8(kids) :
	return ("route", )
	

# action 9 for: [(8) NoRptStmt -> HELP]
def action9(kids) :
	return ("help", )
	

# action 10 for: [(9) tsid -> NUMBER COLON NUMBER]
def action10(kids) :
	return "%i:%i" % (kids[0], kids[2])
	
goto = {(12, 5): 15, (0, 'WATCH'): 6, (12, 'LIST'): 3, (12, 'ROUTE'): 5, (10, 'COLON'): 14, (12, 'INSPECT'): 2, (6, 'INSPECT'): 2, (6, 'LIST'): 3, (6, 7): 9, (12, 6): 15, (6, 'QUIT'): 4, (12, 'QUIT'): 4, (12, 'HELP'): 1, (0, 'ROUTE'): 5, (2, 'NUMBER'): 10, (0, 8): 9, (2, 9): 11, (0, 2): 8, (0, 3): 8, (0, 0): 7, (0, 1): 7, (0, 6): 9, (0, 7): 9, (0, 4): 9, (0, 5): 9, (6, 8): 9, (6, 'ROUTE'): 5, (6, 'NUMBER'): 12, (6, 0): 13, (6, 1): 13, (6, 2): 8, (6, 3): 8, (6, 4): 9, (6, 'HELP'): 1, (6, 6): 9, (6, 5): 9, (0, 'INSPECT'): 2, (0, 'LIST'): 3, (6, 'WATCH'): 6, (0, 'QUIT'): 4, (12, 8): 15, (14, 'NUMBER'): 16, (12, 7): 15, (0, 'HELP'): 1, (12, 4): 15}
action = {(13, '$EOF$'): [('reduce', ('RptStmt', 2, 2))], (11, '$EOF$'): [('reduce', ('NoRptStmt', 2, 6))], (0, 'LIST'): [('shift', 3)], (6, 'ROUTE'): [('shift', 5)], (9, '$EOF$'): [('reduce', ('Stmt', 1, 1))], (10, 'COLON'): [('shift', 14)], (1, '$EOF$'): [('reduce', ('NoRptStmt', 1, 8))], (15, '$EOF$'): [('reduce', ('RptStmt', 3, 3))], (8, '$EOF$'): [('reduce', ('Stmt', 1, 0))], (6, 'NUMBER'): [('shift', 12)], (6, 'INSPECT'): [('shift', 2)], (12, 'ROUTE'): [('shift', 5)], (6, 'QUIT'): [('shift', 4)], (12, 'HELP'): [('shift', 1)], (0, 'ROUTE'): [('shift', 5)], (2, 'NUMBER'): [('shift', 10)], (14, 'NUMBER'): [('shift', 16)], (0, 'HELP'): [('shift', 1)], (12, 'LIST'): [('shift', 3)], (6, 'LIST'): [('shift', 3)], (12, 'INSPECT'): [('shift', 2)], (6, 'HELP'): [('shift', 1)], (12, 'QUIT'): [('shift', 4)], (0, 'INSPECT'): [('shift', 2)], (0, 'WATCH'): [('shift', 6)], (6, 'WATCH'): [('shift', 6)], (0, 'QUIT'): [('shift', 4)], (7, '$EOF$'): [('accept', None)], (5, '$EOF$'): [('reduce', ('NoRptStmt', 1, 7))], (3, '$EOF$'): [('reduce', ('NoRptStmt', 1, 5))], (4, '$EOF$'): [('reduce', ('NoRptStmt', 1, 4))], (16, '$EOF$'): [('reduce', ('tsid', 3, 9))]}
semactions = [action1, action2, action3, action4, action5, action6, action7, action8, action9, action10]
gramspec = (goto, action, semactions)


