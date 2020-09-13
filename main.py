import sublime
import sublime_plugin
import os
import re
from resolve_js_modules.esprima import esprima
import pprint
from datetime import datetime

pluginDir = os.path.dirname(os.path.realpath(__file__))

def log(text):
	logPath = os.path.join(pluginDir, "log.txt")

	with open(logPath, 'a', encoding='utf8') as logFile:
		logFile.write('\n{} > {}'.format(str(datetime.now()), text))

def formatFunction(moduleName, name, params):
	args = []
	if params:
		for param in params:
			if param.type == 'Identifier':
				args.append(param.name)

			if param.type == 'AssignmentPattern' and param.left.type == 'Identifier':
				args.append(param.left.name)

	suggestion = '{}({})\t{}'.format(name, ', '.join(args), moduleName)

	encapped = ['${{{}:{}}}'.format(i+1, name) for i,name in enumerate(args)]
	argString = ', '.join(encapped)
	completed = '{}({})'.format(name, argString)

	return [suggestion, completed]

def getModuleCompletionsFromAst(ast, moduleName):	
	completions = {}

	for node in ast.body:
		if node.type == 'ExportNamedDeclaration':
			if node.declaration and node.declaration.type == 'FunctionDeclaration':
				name = node.declaration.id.name
				completions[name] = formatFunction(moduleName, name, node.declaration.params)

			if node.declaration and node.declaration.type == 'VariableDeclaration':
				for declarator in node.declaration.declarations:
					if declarator.type == 'VariableDeclarator':
						name = declarator.id.name

						if declarator.init and declarator.init.type == 'ArrowFunctionExpression':
							completions[name] = formatFunction(moduleName, name, declarator.init.params)

						else:
							completions[name] = [name + '\t{}'.format(moduleName), name]

	return completions

parseFileCache = {}
def parseFile(filePath):
	if filePath in parseFileCache and os.path.getmtime(filePath) == parseFileCache[filePath][0]:
		return parseFileCache[filePath][1]

	moduleName = os.path.basename(filePath)

	try:
		with open(filePath, encoding='utf8') as file:
			ast = esprima.parseModule(file.read())
			moduleCompletions = getModuleCompletionsFromAst(ast, moduleName)
			parseFileCache[filePath] = (os.path.getmtime(filePath), moduleCompletions)
			return moduleCompletions

	except FileNotFoundError:
		log('File not found: ' + filePath)
		return {}

def findImports(view):
	regex = "import \* as (\w+) from '(\.\.?/.+\.js)'\n"
	importLookahead = 500

	viewHead = view.substr(sublime.Region(0, importLookahead))
	fileDir = os.path.dirname(view.file_name())
	imports = {}
	for (name, filePath) in re.findall(regex, viewHead):
		imports[name] = os.path.abspath(os.path.join(fileDir, filePath))

	return imports

def getCompletions(view, locations):
	imports = findImports(view)

	completions = []

	for point in locations:
		region = view.line(point)
		line = view.substr(region)
		m = re.search('(\w+)\.?(\w*)$', line)
		if not m or m.group() == '':
			continue

		moduleName = m.group(1)
		exportName = m.group(2)

		if moduleName not in imports:
			for key in imports:
				if key.startswith(moduleName):
					completions.append([key + '.js\tmodule', key])

			continue

		moduleCompletions = parseFile(imports[moduleName])
		for key in moduleCompletions.keys():
			if key.startswith(exportName):
				completions.append(moduleCompletions[key])

	return completions

class resolve_js_modules(sublime_plugin.EventListener):
	def on_query_completions(self, view, prefix, locations):
		if 'source.js' not in view.scope_name(0):
			return

		try:
			return getCompletions(view, locations)

		except Exception as e:
			log(e)

		return None