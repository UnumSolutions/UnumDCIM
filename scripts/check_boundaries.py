"""Reject cross-domain Python imports, including dynamic literal imports."""
import ast
from pathlib import Path
root=Path(__file__).resolve().parent.parent
errors=[]
for path in (root/'services').rglob('*.py'):
    owner=path.relative_to(root/'services').parts[0]
    tree=ast.parse(path.read_text())
    for node in ast.walk(tree):
        names=[]
        if isinstance(node,ast.Import): names=[n.name for n in node.names]
        elif isinstance(node,ast.ImportFrom): names=[node.module or '']
        elif isinstance(node,ast.Call) and isinstance(node.func,(ast.Name,ast.Attribute)):
            fn=node.func.id if isinstance(node.func,ast.Name) else node.func.attr
            if fn in ('__import__','import_module') and node.args and isinstance(node.args[0],ast.Constant):names=[str(node.args[0].value)]
        for name in names:
            if name.startswith('services.') and name.split('.')[1]!=owner:
                errors.append(f'{path.relative_to(root)}:{node.lineno}: cross-domain import {name}')
if errors: raise SystemExit('\n'.join(errors))
print('Domain import boundaries verified')
