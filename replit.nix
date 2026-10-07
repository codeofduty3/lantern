{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.python311Packages.pip
    # Poppler/Tesseract are only needed if you re-run the full pipeline on
    # Replit; the API itself serves the pre-computed bundle and needs neither.
    pkgs.poppler_utils
    pkgs.tesseract
  ];
}
