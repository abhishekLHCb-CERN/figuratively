import figuratively as fg
from _toy import histogram_file

f = histogram_file("/tmp/figuratively_toy.root")
fg.plot(f + ":data", f + ":mc", out="../../docs/img/02_data_mc_ratio.png", label="Work in progress",
        labels={"data": "Data", "mc": "Simulation"}, xlabel=(r"$m$", r"MeV/$c^2$"), info="Toy data")
