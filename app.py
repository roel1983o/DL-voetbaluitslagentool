#!/usr/bin/env python3
import io
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import pandas as pd
import numpy as np

app = Flask(__name__)
app.secret_key = "CHANGE-ME"  # set via env in production
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit

def to_clean_str(x):
    if pd.isna(x):
        return ""
    return str(x).strip()

def parse_int_safe(s):
    try:
        if s == "" or s is None:
            return None
        return int(float(str(s).replace(",", ".")))
    except:
        return None

def load_all_sheets(filebytes: bytes) -> pd.DataFrame:
    xls = pd.ExcelFile(io.BytesIO(filebytes))
    frames = []
    for sheet in xls.sheet_names:
        df = pd.read_excel(io.BytesIO(filebytes), sheet_name=sheet, header=0)
        df["__sheet__"] = sheet
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

def find_scorers_column(df: pd.DataFrame):
    # 1) header match
    candidates = [c for c in df.columns if isinstance(c,str) and any(k in c.lower() for k in ["doelpunt","makers","scorer"])]
    if candidates:
        return df[candidates[0]].apply(to_clean_str)
    # 2) heuristiek: meest tekstuele kolom > index 10
    best_i, best_score = None, -1
    for i, c in enumerate(df.columns):
        if i <= 10:
            continue
        s = df[c]
        cnt = 0
        for val in s.dropna().astype(str).values[:500]:
            try:
                float(val.replace(",", "."))
            except:
                cnt += 1
        if cnt > best_score:
            best_score, best_i = cnt, i
    if best_i is not None:
        return df.iloc[:, best_i].apply(to_clean_str)
    return pd.Series([""]*len(df), name="Doelpuntenmakers")

def looks_like_division(text: str) -> bool:
    t = str(text or "").strip().lower()
    return ("divisie" in t) or ("klasse" in t)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        uploaded = request.files.get("file")
        if not uploaded or uploaded.filename == "":
            flash("Kies een Excelbestand (.xlsx).")
            return redirect(url_for("index"))
        if not uploaded.filename.lower().endswith(".xlsx"):
            flash("Alleen .xlsx-bestanden worden geaccepteerd.")
            return redirect(url_for("index"))
        try:
            data = uploaded.read()
            raw = load_all_sheets(data)
            if raw.empty:
                flash("Kon geen data vinden in het Excelbestand.")
                return redirect(url_for("index"))

            def get_col(df, idx, fallback):
                return df.iloc[:, idx].apply(to_clean_str) if df.shape[1] > idx else pd.Series([""]*len(df), name=fallback)

            home = get_col(raw, 1, "Thuisclub")
            away = get_col(raw, 3, "Uitclub")
            hg   = get_col(raw, 5, "ThuisGoals")
            ag   = get_col(raw, 7, "UitGoals")
            hht  = get_col(raw, 8, "RustThuis")
            aht  = get_col(raw, 10, "RustUit")
            scor = find_scorers_column(raw)

            lines = ["<body>"]
            # check kolomkop van 2e kolom
            second_col_header = str(raw.columns[1]) if len(raw.columns) > 1 else ""
            current_div = second_col_header.upper() if looks_like_division(second_col_header) else None
            emitted_div = False

            n = len(raw)
            for i in range(n):
                home_cell = home.iloc[i]
                away_cell = away.iloc[i]
                hg_raw = hg.iloc[i]
                ag_raw = ag.iloc[i]
                hht_raw = hht.iloc[i]
                aht_raw = aht.iloc[i]
                scorers = scor.iloc[i] if i < len(scor) else ""

                # header in 2e kolom?
                if looks_like_division(home_cell):
                    current_div = home_cell.upper()
                    emitted_div = False
                    continue

                # echte wedstrijd?
                if not (home_cell and home_cell.strip()) or not (away_cell and away_cell.strip()):
                    continue

                if current_div and not emitted_div:
                    lines.append(f"<subhead_lead>{current_div}</subhead_lead>")
                    emitted_div = True

                postponed = ("afg" in hg_raw.lower()) or ("gest" in hg_raw.lower())
                hg_num = parse_int_safe(hg_raw)
                ag_num = parse_int_safe(ag_raw)
                if not postponed and hg_num == 0 and ag_num == 0:
                    scorers = " "

                if postponed:
                    subhead = f"<subhead>{home_cell} - {away_cell} {hg_raw}</subhead>"
                else:
                    tg = 0 if hg_num is None else int(hg_num)
                    ug = 0 if ag_num is None else int(ag_num)
                    rth = 0 if parse_int_safe(hht_raw) is None else int(parse_int_safe(hht_raw))
                    rut = 0 if parse_int_safe(aht_raw) is None else int(parse_int_safe(aht_raw))
                    subhead = f"<subhead>{home_cell} - {away_cell} {tg}-{ug} ({rth}-{rut})</subhead>"

                lines.append(subhead)
                lines.append("<howto_facts>")
                lines.append(scorers)
                lines.append("</howto_facts>")

            lines.append("</body>")
            output = "\n".join(lines).encode("utf-8")

            return send_file(io.BytesIO(output), as_attachment=True, download_name="uitslagen_output.txt", mimetype="text/plain; charset=utf-8")
        except Exception as e:
            flash(f"Er ging iets mis: {e}")
            return redirect(url_for("index"))

    return render_template("index.html")

if __name__ == "__main__":
    # For local run; production uses gunicorn
    app.run(host="0.0.0.0", port=5000, debug=False)
