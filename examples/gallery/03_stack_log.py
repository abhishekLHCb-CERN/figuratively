import figuratively as fg
from _toy import roofit_frame

fg.plot(roofit_frame(), out="../../docs/img/03_stack_log.png", label="Work in progress", stack=True,
        logy=True, xlabel=(r"$m_{\gamma\gamma}$", r"MeV/$c^2$"), info="Toy data")
