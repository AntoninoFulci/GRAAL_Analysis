# Compile from this directory so latexmk loads this local configuration.
# Match the reference project's SyncTeX setting; keep generated files outside docs.
$pdf_mode = 1;
# Isolate current auxiliaries from the pre-existing draft.bbl beside the source.
$jobname = 'method';
$out_dir = '../../../results_test/method-paper-preservation-20261111/build';
$pdflatex = 'pdflatex -interaction=nonstopmode -halt-on-error -file-line-error -synctex=1 %O %S';

# Prefer the complete MacTeX installation when it is available.
if (-d '/Library/TeX/texbin') {
    $ENV{'PATH'} = '/Library/TeX/texbin:' . $ENV{'PATH'};
}

# Keep long output paths intact in the verification log.
$ENV{'max_print_line'} = 1000;
