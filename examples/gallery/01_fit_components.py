import figuratively as fg
from _toy import roofit_frame

LABELS = {"sig": r"$X\to\gamma\gamma$ (core)", "tail": r"$X\to\gamma\gamma$ (tail)", "comb": "Combinatorial",
          "bkg_a": "Background A", "bkg_b": "Background B", "bkg_c": "Background C"}
fg.plot(roofit_frame(), out="../../docs/img/01_fit_components.png", label="Work in progress",
        labels=LABELS, xlabel=(r"$m_{\gamma\gamma}$", r"MeV/$c^2$"), info="Toy data", nparams=14)
