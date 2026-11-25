"""Regenerate roofit_toy.root, the fixture written by real ROOT (toy data only; CI has no ROOT).

Usage, from this folder, in an environment with PyROOT:   python make_roofit_toy.py

Objects: the RooPlots "frame", "frame_named" (custom curve names, one invisible curve), "frame_empty" and
"fits/with_params" (in a subfolder, with a paramOn box), a TH1F "h_float", and the canvases
"c_auto", "c_named" and "c_band" (with a VisualizeError band).
"""
import os

import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.RooMsgService.instance().setGlobalKillBelow(ROOT.RooFit.WARNING)
R = ROOT.RooFit
ROOT.RooRandom.randomGenerator().SetSeed(11)
w = ROOT.RooWorkspace("w")
w.factory("Gaussian::sig(x[1750,1980], 1865, 12)")
w.factory("Exponential::bkg(x, -0.006)")
w.factory("SUM::model(f[0.4,0,1]*sig, bkg)")
x, model = w.var("x"), w.pdf("model")
x.setBins(30)
data = model.generate(ROOT.RooArgSet(x), 3000)
result = model.fitTo(data, R.Save(True), R.PrintLevel(-1))


def frame(named=False, band=False, invisible=False):
    fr = x.frame()
    data.plotOn(fr)
    if band:
        model.plotOn(fr, R.VisualizeError(result, 1))
    name = (lambda n: [R.Name(n)]) if named else (lambda n: [])
    if invisible:
        model.plotOn(fr, R.Name("hidden"), R.Invisible())
    model.plotOn(fr, *name("total"))
    model.plotOn(fr, R.Components("sig"), R.LineStyle(2), R.LineColor(ROOT.kRed), *name("signal"))
    model.plotOn(fr, R.Components("bkg"), R.LineStyle(3), *name("background"))
    return fr


keep = []
out = ROOT.TFile("roofit_toy.root", "RECREATE")  # a bare file name: no local path is stored in the file
frame().Write("frame")
frame(named=True, invisible=True).Write("frame_named")
x.frame().Write("frame_empty")
for key, kwargs in (("c_auto", {}), ("c_named", {"named": True}), ("c_band", {"band": True})):
    fr = frame(**kwargs)
    canvas = ROOT.TCanvas(key, key)
    fr.Draw()
    canvas.Update()
    out.cd()
    canvas.Write(key)
    keep.append((fr, canvas))
folder = out.mkdir("fits")
folder.cd()
fr = frame()
model.paramOn(fr)
fr.Write("with_params")
out.cd()
histogram = ROOT.TH1F("h_float", "h_float", 10, 0, 1)
histogram.Write()
uuids = {out.GetUUID().AsString(), folder.GetUUID().AsString()}
out.Close()

# ROOT's file UUID encodes an identifier of the machine that wrote it; blank every copy of it.
blob = open("roofit_toy.root", "rb").read()
for uuid in uuids:
    raw = bytes.fromhex(uuid.replace("-", ""))
    assert raw in blob
    blob = blob.replace(raw, b"\0" * len(raw))
open("roofit_toy.root", "wb").write(blob)
print("wrote roofit_toy.root with ROOT", ROOT.gROOT.GetVersion(), flush=True)
os._exit(0)  # skip PyROOT teardown, which can crash with drawn frames
