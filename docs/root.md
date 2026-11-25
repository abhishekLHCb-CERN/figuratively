# Using it with ROOT

Figuratively never needs ROOT, but it works alongside it.

## From PyROOT

```python
import ROOT, figuratively as fg
fg.plot(canvas)               # a TCanvas, TPad, TH1, TH2, TGraph or RooPlot you just made
fg.plot(h_data, h_mc)         # overlay with a ratio panel
```
ROOT writes the object to a temporary file and Figuratively reads that file, so every feature behaves as for a saved file.

## From a ROOT macro or C++ program

```bash
figly header figuratively.h
```
```cpp
#include "figuratively.h"
Figuratively::Plot(canvas, {"logy=True", "label=Work in progress"});
```
Without the header: `canvas->SaveAs("c.root"); gSystem->Exec("figly c.root");`

!!! note "What is tested"
    CI has no ROOT installation. The PyROOT path and the C++ header are tested against stand-ins (a fake `ROOT`
    module; ROOT-like headers the C++ compiles against, including a shell-injection test). The file path, which both
    use underneath, is tested on real ROOT files.
