import ast
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from plotting_claim_audit.audit import audit, claims, evidence, main
from plotting_claim_audit import phrases

EXPECTED = (('generates charts', 'plots data', 'creates plots', 'visualizes data', 'data visualization', 'plots results', 'generates plots', 'plotting support', 'supports plotting', 'line chart', 'bar chart', 'scatter plot', 'histogram', 'plots a graph', 'draws charts', 'renders charts', 'interactive charts', 'chart generation', 'plot generation', 'visualizes results', 'generates graphs', 'creates charts', 'plots graphs', 'graph generation', 'data charts', 'plots the data', 'charts the data', 'produces charts', 'produces plots', 'plot support', 'chart support', 'supports charts', 'charting support', 'plotting capability', 'charting capability', 'generates a chart', 'generates a plot', 'creates a chart', 'creates a plot', 'draws a chart', 'draws a plot', 'renders a chart', 'renders a plot', 'visualization support', 'supports visualization', 'interactive plots', 'interactive graphs', 'generates visualizations', 'creates visualizations', 'visualizes the data', 'plots the results'), ('no charts', 'does not generate charts', 'does not plot', 'without charts', 'no plotting', 'does not create charts', 'no chart generation', 'does not visualize data', 'no data visualization', 'without plotting', 'does not support plotting', 'plotting not supported', 'no graphs', 'does not generate plots', 'no plot generation', 'does not draw charts', 'cannot plot', 'never plots', 'no visualization', 'does not produce charts', 'no interactive charts', 'does not render charts', 'text only output', 'no graphical output'))

class AuditTests(unittest.TestCase):
    def test_phrase_oracle(self):
        tree = ast.parse(Path(phrases.__file__).read_text())
        actual = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)}
        self.assertEqual((actual['PLOT'], actual['NOPLOT']), EXPECTED)
        # The spec PLOT list contains 51 entries (header corrected from 50).
        self.assertEqual(tuple(map(len, EXPECTED)), (51, 24))

    def test_phrases(self):
        for phrase in EXPECTED[0]:
            with self.subTest(phrase=phrase):
                self.assertEqual(claims(phrase), (True, False))
        for phrase in EXPECTED[1]:
            with self.subTest(phrase=phrase):
                self.assertEqual(claims(phrase), (False, True))
        self.assertEqual(claims("doesn't generate charts"), (False, True))
        self.assertEqual(claims('```\nplots data\n```'), (False, False))
        self.assertEqual(claims('   ~~~~text\nplots data\n   ~~~~'), (False, False))
        self.assertEqual(claims('`plots data`'), (True, False))
        self.assertEqual(claims('plots\n\ndata'), (False, False))

    def test_routes(self):
        samples = [
            'import matplotlib.pyplot as plt; plt.plot(x)',
            'import matplotlib.pyplot as plt; plt.hist(x)',
            'from matplotlib import pyplot as p; p.hist(x)',
            'import matplotlib.pyplot; matplotlib.pyplot.hist(x)',
            'fig, ax = subplots(); ax.plot(x)',
            'fig, ax = subplots(); ax.hist(x)',
            'fig, axs = subplots(); axs[0].hist(x)',
            'ax = fig.add_subplot(); ax.hist(x)',
            'ax = subplots(); ax.hist(x)',
            'sns.lineplot(x)',
            'from seaborn import lineplot as lp; lp(x)',
            'import plotly.express as px; px.scatter(x)',
            'from plotly import express as px; px.line(x)',
            'import plotly.express as px; px.line(x)',
            'from plotly.express import line as ln; ln(x)',
            'import plotly.graph_objects as go; f = go.Figure(); f.add_trace(x)',
            'from plotly import graph_objects as go; f = go.Figure(); f.add_trace(x)',
            'from plotly.graph_objects import Figure as F; f = F(); f.add_scatter(x)',
            'from matplotlib.pyplot import subplots as sp; fig, ax = sp(); ax.hist(x)',
            'import altair as alt; c = alt.Chart(x); c.mark_point()',
            'from bokeh.plotting import figure; p = figure(); p.line(x)',
            'import pygal; c = pygal.Line(); c.add(x)',
            'import seaborn as sns; g = sns.FacetGrid(x); g.map(f)',
            'x.plot(x)', 'x.create_chart(x)',
            'from custom import render_chart as draw; draw(x)',
        ]
        for source in samples:
            with self.subTest(source=source):
                self.assertTrue(evidence(source))

    def test_not_evidence(self):
        samples = ['import matplotlib.pyplot as plt', 'plt.figure()', 'plt.subplots()',
                   'plt.savefig(x)', 'plt.show()', 'plt.title(x)', 'plt.xlabel(x)',
                   'plt.ylabel(x)', 'plt.legend()', 'plt.grid()', 'plt.tight_layout()',
                   'import plotly.graph_objects as go; f = go.Figure()',
                   'import altair as alt; c = alt.Chart(x)',
                   'from bokeh.plotting import figure; p = figure()',
                   'import pygal; c = pygal.Line()',
                   'import seaborn as sns; g = sns.FacetGrid(x)',
                   'f.add_trace(x)', 'c.mark_point()', 'p.line(x)', 'c.add(x)', 'g.map(x)',
                   'pandas.read_csv(x)', 'open(x).read()', 'subprocess.run(["gnuplot"])',
                   '"plt.plot(x)"', '# plt.plot(x)', 'plt.plot', 'bad =', 'render_chart(x)',
                   'lineplot(x)', 'px.line(x)',
                   'import matplotlib.pyplot as plt\ndef hist(x): pass\nplt.hist(x)',
                   'import seaborn\ndef lineplot(x): pass\nsns.lineplot(x)',
                   'def plot(x): pass\nx.plot(x)',
                   'def create_chart(x): pass\nx.create_chart(x)',
                   'from custom import render_chart as draw\ndef render_chart(x): pass\ndraw(x)']
        for source in samples:
            with self.subTest(source=source):
                self.assertFalse(evidence(source))

    def run_case(self, doc, files, options=()):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'README.md').write_text(doc)
            for name, text in files.items():
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = main(['audit', directory, '--json'] + list(options))
            return status, json.loads(output.getvalue())

    def test_findings(self):
        cases = [('plots data', {'app.py':'x.plot(x)'}, (), 0, None, None),
                 ('plots data', {'app.py':'pass'}, (), 2, 'documented-plotting-claim-false', 'HIGH'),
                 ('plots data', {'tests/test_x.py':'x.plot(x)'}, (), 0, 'documented-plotting-claim-false', 'MEDIUM'),
                 ('plots data', {'tests/test_x.py':'x.plot(x)'}, ('--fail-on','medium'), 2, 'documented-plotting-claim-false', 'MEDIUM'),
                 ('no plotting', {'app.py':'x.plot(x)'}, (), 2, 'documented-no-plotting-claim-false', 'HIGH'),
                 ('plain tool', {'app.py':'x.plot(x)'}, (), 0, None, None),
                 ('plots data', {}, (), 2, 'documented-plotting-claim-false', 'HIGH'),
                 ('no plotting', {}, (), 0, None, None)]
        for doc, files, options, code, rule, severity in cases:
            with self.subTest(doc=doc, files=files):
                status, result = self.run_case(doc, files, options)
                self.assertEqual(status, code)
                self.assertIn('verdict', result)
                if rule:
                    self.assertEqual(len(result['findings']), 1)
                    self.assertEqual(result['findings'][0]['rule'], rule)
                    self.assertEqual(result['findings'][0]['severity'], severity)
                    self.assertTrue(result['findings'][0]['message'])
                else:
                    self.assertEqual(result['findings'], [])

    def test_exclusions(self):
        for name in ['fixtures/a.py', 'docs/a.py', 'examples/a.py', 'test_a.py', 'a_test.py', 'tests/a.py']:
            code, result = self.run_case('plots data', {name:'x.plot(x)'})
            self.assertTrue(result['findings'])
            self.assertEqual(result['findings'][0]['severity'], 'MEDIUM' if name.startswith('test') or name == 'a_test.py' else 'HIGH')
        self.assertEqual(self.run_case('plots data', {'skip/a.py':'x.plot(x)'}, ('--ignore','skip'))[0], 2)

    def test_pairs_do_not_cross_modules(self):
        for prefix, construction, operation in [
            ('import plotly.graph_objects as go', 'f=go.Figure()', 'f.add_trace(x)'),
            ('import altair as alt', 'f=alt.Chart(x)', 'f.mark_point()'),
            ('from bokeh.plotting import figure', 'f=figure()', 'f.line(x)'),
            ('import pygal', 'f=pygal.Line()', 'f.add(x)'),
            ('import seaborn as sns', 'f=sns.FacetGrid(x)', 'f.map(x)')]:
            self.assertEqual(self.run_case('plots data', {'a.py':prefix+';'+construction, 'b.py':prefix+';'+operation})[0], 2)

    def test_symlinks_and_docs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'README.md').write_text('plots data')
            (root/'examples').mkdir()
            (root/'examples/a.py').write_text('x.plot(x)')
            (root/'link.py').symlink_to(root/'examples/a.py')
            (root/'linked').symlink_to(root/'examples', target_is_directory=True)
            self.assertEqual(audit(root)['findings'][0]['severity'], 'HIGH')
        self.assertEqual(self.run_case('', {'nested/docs/guide.md':'plots data'})[0], 2)

    def test_cli(self):
        result = subprocess.run([sys.executable, '-m', 'plotting_claim_audit', '--version'], capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, '0.1.0'))
        for args in [[], ['audit', '/definitely/missing'], ['audit', '--bad'], ['audit', '--fail-on', 'low']]:
            with contextlib.redirect_stderr(io.StringIO()):
                try:
                    status = main(args)
                except SystemExit as exc:
                    status = exc.code
            self.assertEqual(status, 1)

if __name__ == '__main__':
    unittest.main()
