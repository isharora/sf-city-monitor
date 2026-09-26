"""Extract per-page text from review PDFs in data/reviews/pdfs/ into data/reviews/text/<name>.txt
Pages are separated by lines '=== PAGE n ===' (1-based PDF page index)."""
import pathlib, pypdf
base = pathlib.Path(__file__).resolve().parents[1] / "data" / "reviews"
out = base / "text"; out.mkdir(exist_ok=True)
for pdf in sorted((base / "pdfs").glob("*.pdf")):
    dst = out / (pdf.stem + ".txt")
    if dst.exists() and dst.stat().st_mtime > pdf.stat().st_mtime:
        continue
    try:
        r = pypdf.PdfReader(str(pdf))
        parts = [f"=== PAGE {i+1} ===\n{(p.extract_text() or '')}" for i, p in enumerate(r.pages)]
        dst.write_text("\n".join(parts))
        print(pdf.name, len(r.pages), "pages")
    except Exception as e:
        print("FAIL", pdf.name, e)
