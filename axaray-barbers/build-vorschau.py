"""Baut vorschau.html: eine einzelne Datei mit allen Bildern, Styles und Skripten (zum Teilen/Ansehen)."""
import base64, re, pathlib
root = pathlib.Path(__file__).parent
MIME = {".jpg": "image/jpeg", ".png": "image/png", ".glb": "model/gltf-binary"}
def data_uri(rel):
    p = root / rel
    return f"data:{MIME[p.suffix]};base64," + base64.b64encode(p.read_bytes()).decode()
def inline_assets(text):
    return re.sub(r"(img|model)/[\w.-]+\.(?:jpg|png|glb)", lambda m: data_uri(m.group(0)), text)
html = (root / "index.html").read_text()
html = html.replace('<link rel="stylesheet" href="styles.css">', "<style>" + (root / "styles.css").read_text() + "</style>")
for js in ["config.js", "ax3d.js", "head.js", "app.js", "tour.js"]:
    html = html.replace(f'<script src="{js}"></script>', "<script>" + (root / js).read_text() + "</script>")
html = html.replace('<link rel="manifest" href="manifest.webmanifest">\n', "")  # als Einzeldatei nicht installierbar
html = re.sub(r"(img|model|icons)/[\w.-]+\.(?:jpg|png|glb)", lambda m: data_uri(m.group(0)), html)
(root / "vorschau.html").write_text(html)
print(f"vorschau.html: {len(html) // 1024} KB")
