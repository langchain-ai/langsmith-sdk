from pydoc_markdown.contrib.loaders.python import PythonLoader
from pydoc_markdown.contrib.processors.filter import FilterProcessor
from pydoc_markdown.contrib.renderers.docusaurus import DocusaurusRenderer
from pydoc_markdown.interfaces import Context

context = Context(directory=".")
loader = PythonLoader(search_path=["langsmith"], modules=["client"])

renderer = DocusaurusRenderer()


loader.init(context)
renderer.init(context)

modules = list(loader.load())
FilterProcessor().process(modules, None)
renderer.render(modules)
