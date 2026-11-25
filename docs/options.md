# All options

Generated from the option registry (`fg.options()` prints the same list).

**Fit components**

| Option | Effect |
|---|---|
| `components` | per-component style: {'sig': 'red dashed fill', 'bkg*': {'alpha': .4}} |
| `labels` | rename legend entries: {'sig': 'Signal', 'data': 'Data', 'total': 'Fit'} or just a list in legend order ['Data', 'Fit', 'Signal', ...] |
| `colors` | colour per object or component: {'sig': '#0072B2'} |
| `styles` | full per-component style dicts: {'comb': {'kind': 'fill', 'hatch': '//'}} |
| `comp_kind` | default drawing style of every component: 'line', 'fill' or 'band' |
| `merge` | sum several components into one entry: {'Backgrounds': ['comb', 'bkg*']} |
| `hide` | regular expressions of components to leave out |
| `order` | component order in the legend and the stack |
| `stack` | stack the components as filled areas |
| `root_colors` | True takes colours, line styles and fills from the ROOT objects (refined, and kept visibly apart); 'components' leaves the total in the house colour; False ignores ROOT |
| `palette` | colours for components without a ROOT colour: figuratively, r4, okabe-ito, tableau10, dark2, hcl |

**Panels**

| Option | Effect |
|---|---|
| `pull` | False to drop the pull panel, or a dict of Plot.pull options: {'ylim': (-4, 4), 'mode': 'centre'}; the range grows beyond +-5 by itself when the pulls are larger |
| `nparams` | number of fit parameters; adds chi2/ndf to the info block |
| `ratio` | False to drop the ratio panel, or its y-range: (0.7, 1.3) |
| `pull_label` | y-label of the pull panel |
| `ratio_label` | y-label of the ratio panel |

**Histograms**

| Option | Effect |
|---|---|
| `normalise` | normalise every histogram to unit area |
| `rebin` | merge N neighbouring bins |
| `kind` | drawing style of histograms: 'step', 'fill', 'points' or 'band' |
| `data_pattern` | regular expression that marks an object as data |

**Regions, lines and text**

| Option | Effect |
|---|---|
| `blind` | hide data in a window and mark it: (1840, 1890) or [(a, b), (c, d)] |
| `blind_curves` | with blind=: also blank the model curves inside the window |
| `vline` | vertical line(s): 1865, (1865, 'label') or a list of those |
| `hline` | horizontal line(s): 100, (100, 'label') or a list of those |
| `span` | shaded window(s): (x0, x1) or (x0, x1, 'label') or a list of those |
| `text` | text at axes fractions: (0.05, 0.9, 'text') or a list of those |
| `canvas_text` | text written on the canvas (e.g. the bin range): True shows it, False hides it, a dict {old: new} edits it, a function f(text, panel) rewrites it (return None to drop) |
| `blind_label` | text inside a blinded band (a window can also carry its own: (lo, hi, 'text')) |
| `info` | small text lines in the top-right block (string or list) |
| `label` | top-left label text, e.g. 'Work in progress' (none by default) |
| `exp` | collaboration name in the label; empty by default, set it only if you are entitled to |
| `com` | centre-of-mass energy in TeV for the label, e.g. '13' |
| `lumi` | integrated luminosity in fb^-1 for the label |
| `data` | False prints 'Simulation' in the label |

**Axes**

| Option | Effect |
|---|---|
| `ylabel_prefix` | start of the automatic y-label, e.g. 'Events' gives 'Events / (2 MeV)' |
| `xlim` | x range (lo, hi); None keeps a side automatic |
| `ylim` | y range (lo, hi) |
| `xrange` | alias of xlim |
| `yrange` | alias of ylim |
| `logx` | logarithmic x axis |
| `logy` | logarithmic y axis |
| `log` | 'x', 'y' or 'xy': shorthand for logx / logy |
| `xlabel` | x label, or (text, unit) |
| `ylabel` | y label (default is generated from the bin width) |
| `unit` | unit used in the axis labels and the bin-width label |
| `scale_x` | multiply the x axis, e.g. 1e-3 for MeV to GeV (set unit= too) |
| `title` | figure title |
| `grid` | draw a grid |
| `headroom` | factor of free space above the data |

**Figure**

| Option | Effect |
|---|---|
| `preset` | a named bundle of settings: thesis, paper, slides, poster, or one of your own from the [presets.NAME] tables of figuratively.toml; the call's own keywords always win |
| `presets` | your own presets as a dict {name: {option: value}} (usually written in figuratively.toml) |
| `size` | figure size (w, h) in inches or a preset: 'column', 'double', 'slide' |
| `figsize` | alias of size |
| `font` | scale every text size |
| `legend` | False, a location string, or a dict(loc=, ncol=, title=) |
| `style` | mplhep style name or path of a .mplstyle file |
| `data_label` | legend text of the data |
| `total_label` | legend text of the total fit |

**Output**

| Option | Effect |
|---|---|
| `formats` | file formats to write |
| `suffix` | text added to the automatic file name, so variants do not overwrite each other: '_stack_log' |
| `checks` | warn about a curve that does not match the data, huge pulls, a leaking blind window, silent normalisation and objects of the canvas that are not drawn (False silences them) |
| `view` | open the saved figure in your default viewer when done |
| `outdir` | folder for the output, relative to the ROOT file |
| `dpi` | resolution of raster output |
| `transparent` | transparent background |
| `strict` | turn warnings about unmatched names into errors |
