// figuratively.h : draw ROOT objects with Figuratively straight from a ROOT macro or a C++ program.
//
//   Get this file:      figly header figuratively.h
//   In a macro:         #include "figuratively.h"
//                       Figuratively::Plot(canvas);                      // TCanvas, TPad, TH1, TGraph, RooPlot ...
//                       Figuratively::Plot(canvas, {"logy=True", "label=Work in progress"});
//   Or without the header, from any macro:
//                       canvas->SaveAs("c.root"); gSystem->Exec("figly c.root");
//
// Needs the `figly` command on the PATH:  pip install figuratively
// Each keyword is an option of fg.plot written as key=value (see `figly options`).

#pragma once
#include <cstdio>
#include <string>
#include <vector>

#include "TDirectory.h"
#include "TFile.h"
#include "TObject.h"
#include "TString.h"
#include "TSystem.h"

namespace Figuratively {

// Single-quote a string for the shell.
inline std::string Quote(const std::string &s) {
  std::string r = "'";
  for (char c : s) {
    if (c == '\'')
      r += "'\\''";
    else
      r += c;
  }
  return r + "'";
}

inline std::string KeywordArgs(const std::vector<std::string> &keywords) {
  std::string args;
  for (const auto &kv : keywords) args += " -s " + Quote(kv);
  return args;
}

// Write `obj` to a temporary ROOT file and run `figly` on it.
// The plots are written to <outdir>/<object name>.pdf and .png (a canvas with several panels gives _1, _2 ...).
// Returns the exit status of figly (0 on success).
inline int Plot(TObject *obj, const std::vector<std::string> &keywords = {}, const std::string &outdir = ".") {
  if (!obj) return 1;
  const std::string name = (obj->GetName() && *obj->GetName()) ? obj->GetName() : "object";
  // A unique file created atomically (mkstemp), so a predictable name in a shared /tmp cannot be hijacked.
  TString base;
  FILE *created = gSystem->TempFileName(base, nullptr, ".root");
  if (!created) return 1;
  fclose(created);
  const std::string tmp = base.Data();
  {
    TDirectory *previous = gDirectory;  // do not disturb the caller's current directory
    TFile file(tmp.c_str(), "RECREATE");
    obj->Write(name.c_str());
    file.Close();
    if (previous) previous->cd();
  }
  const std::string cmd = "figly " + Quote(tmp + ":" + name) + " -o " + Quote(outdir + "/" + name) + KeywordArgs(keywords);
  const int status = gSystem->Exec(cmd.c_str());
  gSystem->Unlink(tmp.c_str());
  return status;
}

// Plot every object of an existing ROOT file.
inline int Plot(const std::string &rootFile, const std::vector<std::string> &keywords = {},
                const std::string &outdir = ".") {
  const std::string cmd = "figly " + Quote(rootFile) + " -s " + Quote("outdir=" + outdir) + KeywordArgs(keywords);
  return gSystem->Exec(cmd.c_str());
}

}  // namespace Figuratively
