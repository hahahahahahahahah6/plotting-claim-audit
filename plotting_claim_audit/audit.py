"""Offline documentation and syntax inspection."""
import argparse
import ast
import json
import re
import sys
from pathlib import Path
from .phrases import PLOT, NOPLOT

PLOT_METHODS = set('plot scatter bar barh hist pie imshow boxplot violinplot errorbar fill_between step stem hexbin contour contourf quiver stackplot eventplot broken_barh spy matshow pcolor pcolormesh specgram loglog semilogx semilogy polar fill vlines hlines'.split())
SEABORN = set('lineplot scatterplot barplot histplot boxplot violinplot heatmap relplot displot catplot jointplot pairplot kdeplot rugplot stripplot swarmplot pointplot countplot lmplot residplot regplot clustermap'.split())
EXPRESS = set('line scatter bar histogram box violin pie imshow density_heatmap density_contour strip ecdf area funnel timeline sunburst treemap icicle parallel_coordinates parallel_categories choropleth scatter_geo line_geo scatter_ternary line_ternary scatter_polar line_polar bar_polar scatter_matrix scatter_3d line_3d'.split())
GLYPHS = set('line circle scatter rect quad vbar hbar wedge patch multi_line segment ray arc annular_wedge image image_rgba hexbin text asterisk cross diamond inverted_triangle square triangle x y'.split())
CHARTS = set('Line Bar Pie XY Histogram StackedBar StackedLine Radar Dot Funnel Gauge Box Bubble Treemap Worldmap'.split())
GENERIC = set('plot scatter bar_chart line_chart create_plot create_chart draw_plot draw_chart make_plot make_chart render_plot render_chart plot_data plot_results show_plot save_plot plot_graph plot_figure generate_plot generate_chart build_plot build_chart display_plot display_chart'.split())


def normalize(text):
    return ' '.join(text.lower().replace("n't", ' not').replace('-', ' ').split())


def matches(text, phrases):
    pattern = r'\b(?:' + '|'.join(re.escape(p) for p in sorted(phrases, key=lambda p: (-len(p), p))) + r')\b'
    return list(re.finditer(pattern, text))


def claims(text):
    lines = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            lines.append('')
        elif marker:
            fence = marker[1]
            lines.append('')
        else:
            lines.append(line)
    positive, negative = False, False
    for para in re.split(r'\n\s*\n', '\n'.join(lines)):
        text = normalize(para)
        spans = matches(text, NOPLOT)
        negative |= bool(spans)
        for span in reversed(spans):
            text = text[:span.start()] + ' ' * (span.end()-span.start()) + text[span.end():]
        positive |= bool(matches(text, PLOT))
    return positive, negative


def evidence(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    nodes = list(ast.walk(tree))
    imports = set()
    aliases = {}
    for node in nodes:
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.add(a.name)
                aliases[a.asname or a.name.split('.')[0]] = a.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            imports.add(module)
            for a in node.names:
                aliases[a.asname or a.name] = module + '.' + a.name
    def imported(module):
        return any(i == module or i.startswith(module + '.') for i in imports) or any(v == module or v.startswith(module + '.') for v in aliases.values())
    def name(node):
        return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ''
    def resolved(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, '')
        if isinstance(node, ast.Attribute):
            base = resolved(node.value)
            return base + '.' + node.attr if base else ''
        return ''
    shadows = {n.name for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    axes = set()
    bound = {k: set() for k in ('go', 'alt', 'bokeh', 'pygal', 'facet')}
    for node in nodes:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or not isinstance(node.value, ast.Call):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        constructor = resolved(node.value.func).rsplit('.', 1)[-1] or name(node.value.func)
        for target in targets:
            if constructor in ('subplots', 'add_subplot'):
                if isinstance(target, ast.Name):
                    axes.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for item in target.elts[1:]:
                        axes.update(n.id for n in ast.walk(item) if isinstance(n, ast.Name))
            if isinstance(target, ast.Name) and constructor not in shadows and name(node.value.func) not in shadows:
                for key, module, constructors in [('go', 'plotly.graph_objects', {'Figure'}), ('alt', 'altair', {'Chart'}), ('bokeh', 'bokeh.plotting', {'figure'}), ('pygal', 'pygal', CHARTS), ('facet', 'seaborn', {'FacetGrid'})]:
                    if imported(module) and constructor in constructors:
                        bound[key].add(target.id)
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        raw = name(func)
        canonical = resolved(func).rsplit('.', 1)[-1]
        method = raw if isinstance(func, ast.Attribute) else canonical
        if ((isinstance(func, ast.Attribute) and raw in GENERIC) or (isinstance(func, ast.Name) and canonical in GENERIC)) and raw not in shadows and method not in shadows:
            return True
        if imported('plotly.express') and method in EXPRESS:
            return True
        if raw in shadows or method in shadows:
            continue
        if method in SEABORN and (isinstance(func, ast.Attribute) or resolved(func).startswith('seaborn.')):
            return True
        if not isinstance(func, ast.Attribute):
            continue
        base = func.value
        base_name = base.id if isinstance(base, ast.Name) else ''
        if raw in PLOT_METHODS:
            if resolved(base) == 'matplotlib.pyplot' or (ast.unparse(base) == 'matplotlib.pyplot' and imported('matplotlib.pyplot')):
                return True
            axbase = base.value if isinstance(base, ast.Subscript) else base
            if isinstance(axbase, ast.Name) and axbase.id in axes:
                return True
        if ((base_name in bound['go'] and raw.startswith('add_')) or
            (base_name in bound['alt'] and raw.startswith('mark_')) or
            (base_name in bound['bokeh'] and raw in GLYPHS) or
            (base_name in bound['pygal'] and raw == 'add') or
            (base_name in bound['facet'] and raw == 'map')):
            return True
    return False


def audit(root, ignore=()):
    root = Path(root)
    if not root.is_dir():
        raise OSError('root must be a readable directory')
    positive = negative = production = testing = False
    docs = []
    sources = []
    def walk(directory):
        for path in sorted(directory.iterdir()):
            if path.is_symlink():
                continue
            rel = path.relative_to(root).as_posix()
            if any(rel == p.rstrip('/') or rel.startswith(p.rstrip('/') + '/') for p in ignore):
                continue
            if path.is_dir():
                yield from walk(path)
            elif path.is_file():
                yield path
    for path in walk(root):
        rel = path.relative_to(root)
        parts = rel.parts
        if (rel.as_posix() == 'README.md' or 'docs' in parts) and path.suffix == '.md':
            docs.append(rel.as_posix())
            p, n = claims(path.read_text(encoding='utf-8'))
            positive |= p
            negative |= n
        if path.suffix != '.py' or any(p in parts for p in ('fixtures', 'docs', 'examples')):
            continue
        sources.append(rel.as_posix())
        found = evidence(path.read_text(encoding='utf-8'))
        test = 'tests' in parts or path.name.startswith('test_') or path.name.endswith('_test.py')
        if test:
            testing |= found
        else:
            production |= found
    findings = []
    if positive and not production:
        findings.append({'rule': 'documented-plotting-claim-false', 'severity': 'MEDIUM' if testing else 'HIGH', 'message': 'Evidence exists only in tests.' if testing else 'Documentation claim has no production evidence.'})
    if negative and production:
        findings.append({'rule': 'documented-no-plotting-claim-false', 'severity': 'HIGH', 'message': 'Documentation denial conflicts with production evidence.'})
    return {'verdict': 'FAIL' if findings else 'PASS', 'findings': findings, 'docs': docs, 'sources': sources}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, '%s: error: %s\n' % (self.prog, message))


def main(argv=None):
    parser = Parser(prog='plotting-claim-audit')
    parser.add_argument('--version', action='version', version='0.1.0')
    sub = parser.add_subparsers(dest='command', required=True, parser_class=Parser)
    cmd = sub.add_parser('audit')
    cmd.add_argument('repo', nargs='?', default='.')
    cmd.add_argument('--json', action='store_true')
    cmd.add_argument('--verbose', action='store_true')
    cmd.add_argument('--ignore', action='append', default=[])
    cmd.add_argument('--fail-on', choices=['high', 'medium'], default='high')
    args = parser.parse_args(argv)
    try:
        result = audit(args.repo, args.ignore)
    except (OSError, UnicodeError) as exc:
        print('error: %s' % exc, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(result['verdict'])
        for finding in result['findings']:
            print('{severity} {rule}: {message}'.format(**finding))
        if args.verbose:
            print('Documents: %s; sources: %s' % (len(result['docs']), len(result['sources'])))
    return 2 if any(f['severity'] == 'HIGH' or args.fail_on == 'medium' for f in result['findings']) else 0
