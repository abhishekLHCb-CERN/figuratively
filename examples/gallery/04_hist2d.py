import figuratively as fg
from _toy import histogram_file

f = histogram_file("/tmp/figuratively_toy.root")
fg.plot(f + ":corr", out="../../docs/img/04_hist2d.png", label="Work in progress", xlabel="$x$", ylabel="$y$")
