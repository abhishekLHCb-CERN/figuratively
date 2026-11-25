# Authors

- **Abhishek Bohare** (The University of Edinburgh, UK): author and maintainer. Concept, direction, testing against real analysis files, release.

## How it was built

Figuratively was developed by Abhishek Bohare with AI assistance (Claude Code, by Anthropic). The AI wrote and
reviewed code and tests under the author's direction; the author decided what to build, tested the tool on real
RooFit canvases and is responsible for the project. This is stated openly because it is the honest description of
how the software was made.

## Standing on the shoulders of

- [uproot](https://github.com/scikit-hep/uproot5) (reads ROOT files without ROOT) and
  [mplhep](https://github.com/scikit-hep/mplhep) (HEP plot styles), by the Scikit-HEP community;
- [matplotlib](https://matplotlib.org) for all drawing;
- the [ROOT](https://root.cern) and RooFit developers, whose file format and conventions this tool reads;
- [JSROOT](https://github.com/root-project/jsroot), from whose public source the ROOT colour table was extracted;
- R's colour work (the 4.0 default palette, `hcl.colors`, Okabe and Ito's palette), which inspired the colour
  translation.
